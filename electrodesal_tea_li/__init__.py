"""
electrodesal_tea_li
-------------------
Techno-economic analysis (TEA) model for membrane capacitive deionisation
(mCDI) based lithium extraction from geothermal brines.

Computes the Levelised Cost of Lithium (LCOL, $/kg LiOH·H₂O) broken
down by capital and operational cost components.  Also provides
experimental energy analysis utilities for processing raw
voltage–time traces from LFP-vs-AC half-cell cycling experiments.

Typical usage::

    from electrodesal_tea_li import load_params, compute_lcol

    params = load_params()
    result = compute_lcol(params)
    print(f"LCOL = {result.LCOL:.2f} $/kg LiOH·H₂O")
"""

from .initialize import load_params, sensitivity_ranges
from .model import compute_lcol, LCOLResult
from .energy import process_all_cycles, integrate_half_cycle

__all__ = [
    "load_params",
    "sensitivity_ranges",
    "compute_lcol",
    "LCOLResult",
    "process_all_cycles",
    "integrate_half_cycle",
]
