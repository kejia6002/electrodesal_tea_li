"""
sensitivity.py
--------------
One-at-a-time (OAT) sensitivity analysis for the LCOL model.

For each parameter in :func:`~electrodesal_tea_li.initialize.sensitivity_ranges`,
the model is evaluated across a sweep of values while all other parameters
are held at their baseline values.  Results are written to CSV files.

Usage::

    python -m electrodesal_tea_li.sensitivity --outdir results/sensitivity
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

from .initialize import load_params, sensitivity_ranges
from .model import compute_lcol

log = logging.getLogger(__name__)

# Column headers for the output CSV files
_COLUMNS = [
    "VarValue",
    "LCOL", "LCOL_CapEx", "LCOL_OpEx", "SEC",
    "LCOL_Electrode", "LCOL_IEM", "LCOL_OtherCapEx",
    "LCOL_Electricity", "LCOL_OtherOpEx",
    # Detailed CAPEX
    "LCOL_CC_elec", "LCOL_CC_IEM", "LCOL_CC_cc_sp_H",
    "LCOL_CC_BOS", "LCOL_CC_indirect",
    # Detailed OPEX
    "LCOL_OC_electricity", "LCOL_OC_replace_elec",
    "LCOL_OC_replace_IEM", "LCOL_OC_replace_cc_sp_H",
    "LCOL_OC_MLC",
]


def run_single_sensitivity(
    var_name: str,
    var_range: list[float],
    n_points: int = 500,
    config_path: Path | None = None,
) -> pd.DataFrame:
    """
    Sweep *var_name* across *var_range* and return a results DataFrame.

    Parameters
    ----------
    var_name : str
        Parameter key to vary (must exist in the params dict).
    var_range : list of float
        ``[min, max]`` bounds for the sweep.
    n_points : int, optional
        Number of evenly spaced (or log-spaced for ``L_elec``) evaluation
        points.  Default: 500.
    config_path : Path, optional
        Path to the YAML config file.  Defaults to repo-root ``config.yaml``.

    Returns
    -------
    pd.DataFrame
        Shape ``(n_points, len(_COLUMNS))`` with headers from :data:`_COLUMNS`.
    """
    # Log-space for electrode lifespan (spans several orders of magnitude)
    if var_name == "L_elec":
        values = np.geomspace(var_range[0], var_range[1], n_points)
    else:
        values = np.linspace(var_range[0], var_range[1], n_points)

    rows: list[list] = []
    for val in values:
        params = load_params(config_path)
        params[var_name] = val
        try:
            r = compute_lcol(params)
        except Exception as exc:
            log.warning("Skipping %s=%.4g: %s", var_name, val, exc)
            rows.append([val] + [float("nan")] * (len(_COLUMNS) - 1))
            continue

        bd = r.summary_breakdown()
        rows.append([
            val,
            r.LCOL, r.LCOL_CC, r.LCOL_OC, r.SEC,
            bd["LCOL_Electrode"], bd["LCOL_IEM"], bd["LCOL_OtherCapEx"],
            bd["LCOL_Electricity"], bd["LCOL_OtherOpEx"],
            r.LCOL_CC_elec, r.LCOL_CC_IEM, r.LCOL_CC_cc_sp_H,
            r.LCOL_CC_BOS, r.LCOL_CC_indirect,
            r.LCOL_OC_electricity, r.LCOL_OC_replace_elec,
            r.LCOL_OC_replace_IEM, r.LCOL_OC_replace_cc_sp_H,
            r.LCOL_OC_MLC,
        ])

    return pd.DataFrame(rows, columns=_COLUMNS)


def run_all_sensitivity(
    outdir: str | Path,
    n_points: int = 500,
    config_path: Path | None = None,
) -> None:
    """
    Run OAT sensitivity for all parameters and write results to *outdir*.

    One CSV is produced per parameter:
    ``<outdir>/MCDI-baseline_<VarName>.csv``

    Parameters
    ----------
    outdir : str or Path
        Output directory (created if it does not exist).
    n_points : int, optional
        Sweep resolution.  Default: 500.
    config_path : Path, optional
        Path to YAML config file.
    """
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    ranges = sensitivity_ranges()
    for var_name, var_range in ranges.items():
        log.info("Sensitivity sweep: %s  [%.4g, %.4g]", var_name, *var_range)
        df = run_single_sensitivity(var_name, var_range, n_points, config_path)
        fname = outdir / f"MCDI-baseline_{var_name}.csv"
        df.to_csv(fname, index=False)
        log.info("  → %s", fname)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser(
        description="OAT sensitivity analysis for the LCOL model",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--outdir",
        type=Path,
        default=Path("results/sensitivity"),
        help="Output directory for sensitivity CSV files.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to YAML parameter config file.",
    )
    parser.add_argument(
        "--n",
        type=int,
        default=500,
        help="Number of points per sweep.",
    )
    args = parser.parse_args()
    run_all_sensitivity(args.outdir, args.n, args.config)
