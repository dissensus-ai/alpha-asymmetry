#!/usr/bin/env python3
"""Fetch the eight raw input series and check them against the committed manifest.

The raw CSVs are deliberately not committed (see README, "Data"), so a fresh
clone has no inputs until this script is run.  It downloads them into the local
cache and compares each file's SHA-256 against the hashes recorded in
``analysis/data_manifest.json``, so a reader can tell whether they are working
from the same bytes the committed results were produced from.

A mismatch is not automatically a problem.  ``analysis/data_access.py`` records,
per series, whether its bytes can be expected to reproduce: FX spot rates and
index levels carry no corporate-action adjustment and are stable indefinitely,
while a distributing fund requested with ``auto_adjust=True`` has its entire
history rescaled by every new distribution.  This script reports the two cases
separately and only fails on the first.

Usage::

    python analysis/fetch_data.py              # download and verify
    python analysis/fetch_data.py --offline    # verify existing cache only
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

try:
    from analysis.data_access import HASH_STABILITY_NOTES, load_datasets
except ModuleNotFoundError:  # direct execution from analysis/
    sys.path.insert(0, str(REPO_ROOT))
    from analysis.data_access import HASH_STABILITY_NOTES, load_datasets


ANALYSIS_DIR = REPO_ROOT / "analysis"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cache-dir", type=Path, default=ANALYSIS_DIR / "cache",
                        help="where the raw CSVs live (default: analysis/cache)")
    parser.add_argument("--manifest", type=Path, default=ANALYSIS_DIR / "data_manifest.json",
                        help="committed manifest to compare against")
    parser.add_argument("--offline", action="store_true",
                        help="verify the existing cache without downloading")
    parser.add_argument("--write-manifest", type=Path, default=None,
                        help="write the freshly observed manifest to this path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    _, observed = load_datasets(args.cache_dir, refresh=not args.offline,
                                offline=args.offline)
    if args.write_manifest is not None:
        args.write_manifest.write_text(json.dumps(observed, indent=2) + "\n",
                                       encoding="utf-8")

    if not args.manifest.exists():
        print(f"No committed manifest at {args.manifest}; nothing to compare against.")
        return 0
    recorded = json.loads(args.manifest.read_text(encoding="utf-8"))["datasets"]

    print(f"{'SERIES':8} {'SHA-256':10} {'ROWS':>6}  {'WINDOW':<25} EXPECTATION")
    print("-" * 88)
    unexpected: list[str] = []
    explained: list[str] = []
    for name, obs in observed["datasets"].items():
        rec = recorded.get(name)
        stability = obs["hash_stability"]
        window = f"{obs['first_date']}..{obs['last_date']}"
        if rec is None:
            verdict, note = "NEW", "not in the committed manifest"
        elif rec["sha256"] == obs["sha256"]:
            verdict, note = "match", stability
        elif stability == "drifts_with_distributions":
            verdict, note = "differs", f"{stability} (expected)"
            explained.append(name)
        else:
            verdict, note = "DIFFERS", f"{stability} (NOT expected)"
            unexpected.append(name)
        print(f"{name:8} {verdict:10} {obs['rows']:>6}  {window:<25} {note}")
    print("-" * 88)

    if explained:
        print()
        for name in explained:
            print(f"{name}: {HASH_STABILITY_NOTES['drifts_with_distributions']}")

    if unexpected:
        print()
        print("The following series changed but were not expected to:")
        for name in unexpected:
            print(f"  {name}: recorded {recorded[name]['sha256']}")
            print(f"  {' ' * len(name)}  observed {observed['datasets'][name]['sha256']}")
        print()
        print("Investigate before using these inputs. A vendor revision, a different")
        print("package version writing the CSV, or a changed request window can all")
        print("produce this, and they are not equally harmless.")
        return 1

    print()
    print("All series either match the committed manifest or differ for a recorded,")
    print("expected reason. Run the pipeline with --offline to use exactly these files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
