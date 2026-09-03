"""Versioned local-cache access for the replication datasets."""

from __future__ import annotations

import hashlib
import json
import platform
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

import pandas as pd
import yfinance as yf


REPO_ROOT = Path(__file__).resolve().parents[1]
TICKERS = {
    "EURJPY": "EURJPY=X",
    "DXY": "DX-Y.NYB",
    "VIX": "^VIX",
    "AUDJPY": "AUDJPY=X",
    "NZDJPY": "NZDJPY=X",
    "GBPUSD": "GBPUSD=X",
    "SPY": "SPY",
    "GLD": "GLD",
}
START_DATE = "2014-06-01"
END_DATE_EXCLUSIVE = "2025-09-01"

# Whether a series' bytes can be expected to reproduce on a later download.
#
# Series are requested with auto_adjust=True.  For an FX spot rate or an index
# level there is no corporate action and therefore no adjustment factor, so the
# stored history is fixed and the file hash is reproducible indefinitely.  For a
# distributing exchange-traded fund the whole history is back-adjusted every
# time a new distribution is paid, so its hash changes on any download that
# straddles one -- even though no historical observation has been revised and no
# percentage return is affected.  Recording the expectation here keeps a routine
# rescaling from being mistaken for corrupted or revised data.
HASH_STABILITY = {
    "EURJPY": "stable",                      # FX spot, no adjustment factor
    "DXY": "stable",                         # index level, no adjustment factor
    "VIX": "stable",                         # index level, no adjustment factor
    "AUDJPY": "stable",                      # FX spot, no adjustment factor
    "NZDJPY": "stable",                      # FX spot, no adjustment factor
    "GBPUSD": "stable",                      # FX spot, no adjustment factor
    "SPY": "drifts_with_distributions",      # distributing ETF, back-adjusted
    "GLD": "stable_in_window",               # ETF, no cash distributions here
}
HASH_STABILITY_NOTES = {
    "stable": (
        "FX spot rate or index level: no corporate-action adjustment exists, so "
        "the file hash is expected to reproduce exactly on any later download."
    ),
    "stable_in_window": (
        "Adjusted series that made no cash distribution over the requested "
        "window, so the hash is expected to reproduce, but not structurally "
        "guaranteed to the way an unadjusted series is."
    ),
    "drifts_with_distributions": (
        "Distributing fund requested with auto_adjust=True: every new "
        "distribution rescales the entire stored history, so the hash is "
        "expected to change between downloads that straddle one. Percentage "
        "returns are invariant to that rescaling; only the stored price level "
        "and therefore the file bytes move."
    ),
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _portable_path(path: Path) -> str:
    """Keep default-run manifests portable while retaining override clarity."""

    resolved = path.resolve()
    try:
        return resolved.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(resolved)


def _normalise_download(frame: pd.DataFrame) -> pd.DataFrame:
    if isinstance(frame.columns, pd.MultiIndex):
        frame.columns = frame.columns.get_level_values(0)
    if "Close" not in frame.columns:
        raise ValueError("downloaded dataset has no Close column")
    result = frame.copy()
    result.index = pd.to_datetime(result.index).tz_localize(None)
    result.index.name = "Date"
    return result.sort_index()


def _read_csv(path: Path) -> pd.DataFrame:
    result = pd.read_csv(path, index_col="Date", parse_dates=["Date"])
    result.index = pd.to_datetime(result.index).tz_localize(None)
    return result.sort_index()


def load_datasets(
    cache_dir: Path,
    *,
    refresh: bool = False,
    offline: bool = False,
    required: tuple[str, ...] | None = None,
) -> tuple[dict[str, pd.DataFrame], dict]:
    """Load exact local CSVs when present, otherwise retrieve and cache them.

    Raw snapshots are intentionally ignored by Git because Yahoo data may be
    subject to redistribution terms.  The returned manifest records hashes,
    retrieval time, row counts, dates, and the software actually used.
    """

    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    names = required or tuple(TICKERS)
    datasets: dict[str, pd.DataFrame] = {}
    sources: dict[str, dict] = {}
    loaded_at = datetime.now(timezone.utc).isoformat()

    for name in names:
        if name not in TICKERS:
            raise KeyError(f"unknown dataset {name!r}")
        path = cache_dir / f"{name.lower()}.csv"
        metadata_path = path.with_suffix(".metadata.json")
        use_cache = path.exists() and not refresh
        if use_cache:
            frame = _read_csv(path)
            source = "local_cache"
            if metadata_path.exists():
                cache_metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                retrieved_at = cache_metadata.get("retrieved_at_utc")
                retrieval_time_basis = "recorded_at_download"
            else:
                retrieved_at = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()
                retrieval_time_basis = "cache_file_mtime"
        else:
            if offline:
                raise FileNotFoundError(
                    f"offline mode requires cached file: {path}"
                )
            frame = yf.download(
                TICKERS[name],
                start=START_DATE,
                end=END_DATE_EXCLUSIVE,
                interval="1d",
                # Adjusted history keeps exchange-traded series comparable
                # through distributions; FX and index series are unchanged.
                auto_adjust=True,
                progress=False,
                threads=False,
            )
            frame = _normalise_download(frame)
            if frame.empty:
                raise RuntimeError(f"Yahoo Finance returned no rows for {TICKERS[name]}")
            frame.to_csv(path, date_format="%Y-%m-%d")
            source = "yahoo_finance"
            retrieved_at = datetime.now(timezone.utc).isoformat()
            retrieval_time_basis = "recorded_at_download"
            metadata_path.write_text(
                json.dumps(
                    {
                        "ticker": TICKERS[name],
                        "retrieved_at_utc": retrieved_at,
                        "requested_start": START_DATE,
                        "requested_end_exclusive": END_DATE_EXCLUSIVE,
                        "interval": "1d",
                        "auto_adjust": True,
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
        if frame.empty:
            raise ValueError(f"dataset {name} is empty: {path}")
        datasets[name] = frame
        sources[name] = {
            "ticker": TICKERS[name],
            "source": source,
            "path": _portable_path(path),
            "retrieved_at_utc": retrieved_at,
            "retrieval_time_basis": retrieval_time_basis,
            "sha256": _sha256(path),
            "hash_stability": HASH_STABILITY[name],
            "rows": int(len(frame)),
            "first_date": frame.index.min().date().isoformat(),
            "last_date": frame.index.max().date().isoformat(),
        }

    manifest = {
        "manifest_generated_at_utc": loaded_at,
        "requested_start": START_DATE,
        "requested_end_exclusive": END_DATE_EXCLUSIVE,
        "original_snapshot_available": False,
        "original_snapshot_note": (
            "The repository did not contain the raw files used for the committed results; "
            "hashes identify this replication run only."
        ),
        "hash_stability_legend": HASH_STABILITY_NOTES,
        "software": {
            "python": platform.python_version(),
            "numpy": version("numpy"),
            "pandas": version("pandas"),
            "scipy": version("scipy"),
            "statsmodels": version("statsmodels"),
            "yfinance": version("yfinance"),
        },
        "datasets": sources,
    }
    return datasets, manifest


def write_manifest(manifest: dict, path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
