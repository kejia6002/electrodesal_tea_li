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

Explore a different AC:LFP electrode mass ratio without editing
config.yaml (useful while the true AC electrode mass is unconfirmed)::

    python run_model.py --rm 2.0
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


def run(config_path: Path, outdir: Path | None, rm_override: float | None = None) -> None:
    """Load params, run the model, log results, and optionally write CSVs."""
    params = load_params(config_path, overrides={"Rm": rm_override})

    if rm_override is not None:
        log.info("Rm set via --rm: %.3f", rm_override)

    result = compute_lcol(params)

    log.info("=" * 55)
    log.info("  LCOL  = %.4f  $/kg LiOH·H₂O", result.LCOL)
    log.info("  CAPEX = %.4f  $/kg LiOH·H₂O", result.LCOL_CC)
    log.info("  OPEX  = %.4f  $/kg LiOH·H₂O", result.LCOL_OC)
    log.info("  SEC   = %.2f  kWh/kg Li",       result.SEC)
    log.info("-" * 55)
    log.info("  Rm (AC:LFP electrode mass ratio) = %.3f", result.Rm)
    log.info("  M_stack_elec (LFP+AC combined)   = %.3f kg/stack", result.M_stack_elec)
    log.info("    -> LFP side (composite)        = %.3f kg/stack", result.M_stack_elec_LFP)
    log.info("    -> LFP side (pure, 80%% active) = %.3f kg/stack", result.M_stack_pure_LFP)
    log.info("    -> AC side (composite)         = %.3f kg/stack", result.M_stack_elec_AC)
    log.info(
        "  LCOL_CC_elec:  LFP = %.4f  |  AC = %.4f  $/kg",
        result.LCOL_CC_elec_LFP, result.LCOL_CC_elec_AC,
    )
    log.info("-" * 55)
    log.info("  n_stack   = %d",   result.n_stack)
    log.info("  n_module  = %d",   result.n_module)
    log.info("  M_elec    = %.1f kg  (pure LFP demand, sized from ALAR)", result.M_elec)
    log.info("  LiOH/year = %.1f kg/year", result.LiOH_mass_year)
    log.info("=" * 55)

    if outdir is None:
        return

    outdir.mkdir(parents=True, exist_ok=True)

    # Distinguish --rm what-if runs from the baseline so they don't clobber
    # each other in outdir/.
    suffix = f"_Rm{rm_override:g}" if rm_override is not None else ""

    # 1. Top-level summary. summary_breakdown() keeps its original five-bucket
    #    contract (other code, e.g. sensitivity.py, relies on that shape), so
    #    Rm is appended here rather than added to the dataclass method itself.
    summary = result.summary_breakdown()
    summary["Rm"] = result.Rm
    pd.DataFrame([summary]).to_csv(
        outdir / f"MCDI-baseline_LCOL{suffix}.csv", index=False
    )

    # 2. Full CAPEX + OPEX component table. capex_breakdown() now reports
    #    "Electrode (LFP)" and "Electrode (AC)" as separate columns.
    capex_df = pd.DataFrame([result.capex_breakdown()])
    opex_df = pd.DataFrame([result.opex_breakdown()])
    pd.concat([capex_df, opex_df], axis=1).to_csv(
        outdir / f"MCDI-baseline_LCOL_Breakdown{suffix}.csv", index=False
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
    parser.add_argument(
        "--rm",
        type=float,
        default=None,
        help=(
            "Override Rm (AC:LFP electrode mass ratio, M_AC/M_LFP) from "
            "config.yaml, for quick what-if exploration while the true AC "
            "electrode mass is unconfirmed."
        ),
    )
    return parser.parse_args(argv)


def main(argv=None) -> None:
    args = parse_args(argv)
    outdir = None if args.no_save else args.outdir
    log.info("Config: %s", args.config)
    run(args.config, outdir, rm_override=args.rm)


if __name__ == "__main__":
    main()