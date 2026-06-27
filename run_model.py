"""
run_model.py
------------
Command-line entry point for the LCOL techno-economic model.

Runs the baseline LCOL calculation and writes results to the specified
output directory as CSV files.

Examples
--------
Run with default config, saving to ``./results/``::

    python run_model.py

Custom config and output path::

    python run_model.py --config my_config.yaml --outdir /tmp/lcol_results

Print results to console only, no file output::

    python run_model.py --no-save
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))

from electrodesal_tea_li.initialize import load_params
from electrodesal_tea_li.model import compute_lcol

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


def run(config_path: Path, outdir: Path | None) -> None:
    """Load params, run the model, log results, and optionally write CSVs."""
    params = load_params(config_path)
    result = compute_lcol(params)

    log.info("=" * 55)
    log.info("  LCOL  = %.4f  $/kg LiOH·H₂O", result.LCOL)
    log.info("  CAPEX = %.4f  $/kg LiOH·H₂O", result.LCOL_CC)
    log.info("  OPEX  = %.4f  $/kg LiOH·H₂O", result.LCOL_OC)
    log.info("  SEC   = %.2f  kWh/kg Li",       result.SEC)
    log.info("-" * 55)
    log.info("  n_stack   = %d",   result.n_stack)
    log.info("  n_module  = %d",   result.n_module)
    log.info("  M_elec    = %.1f kg", result.M_elec)
    log.info("  LiOH/year = %.1f kg/year", result.LiOH_mass_year)
    log.info("=" * 55)

    if outdir is None:
        return

    outdir.mkdir(parents=True, exist_ok=True)

    # 1. Top-level summary
    pd.DataFrame([result.summary_breakdown()]).to_csv(
        outdir / "MCDI-baseline_LCOL.csv", index=False
    )

    # 2. Full CAPEX + OPEX component table
    capex_df = pd.DataFrame([result.capex_breakdown()])
    opex_df = pd.DataFrame([result.opex_breakdown()])
    pd.concat([capex_df, opex_df], axis=1).to_csv(
        outdir / "MCDI-baseline_LCOL_Breakdown.csv", index=False
    )

    log.info("Results written to %s/", outdir)


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="LCOL techno-economic model for mCDI lithium extraction",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(__file__).parent / "config.yaml",
        help="Path to YAML parameter configuration file.",
    )
    parser.add_argument(
        "--outdir",
        type=Path,
        default=Path(__file__).parent / "results",
        help="Directory for output CSV files.",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Print results to console only; do not write CSV files.",
    )
    return parser.parse_args(argv)


def main(argv=None) -> None:
    args = parse_args(argv)
    outdir = None if args.no_save else args.outdir
    log.info("Config: %s", args.config)
    run(args.config, outdir)


if __name__ == "__main__":
    main()
