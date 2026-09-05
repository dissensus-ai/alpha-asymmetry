#!/usr/bin/env python3
"""Compatibility entry point; the unified pipeline regenerates both figures."""

try:
    from analysis.full_pipeline import main
except ModuleNotFoundError:  # direct execution from analysis/
    from full_pipeline import main


if __name__ == "__main__":
    raise SystemExit(main())
