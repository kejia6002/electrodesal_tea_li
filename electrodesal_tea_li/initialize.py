"""
initialize.py
-------------
Load model parameters from a YAML configuration file.

All baseline values are defined in ``config.yaml`` at the repo root.
The :func:`sensitivity_ranges` function returns the one-at-a-time (OAT)
parameter sweep bounds used by the sensitivity analysis scripts.
"""

from __future__ import annotations

from pathlib import Path

import yaml


def load_params(config_path: str | Path | None = None) -> dict:
    """
    Load and return the baseline parameter dictionary from *config_path*.

    Parameters
    ----------
    config_path : str or Path, optional
        Path to the YAML configuration file.  Defaults to
        ``config.yaml`` two levels above this module (repo root).

    Returns
    -------
    dict
        Parameter dictionary ready for :func:`~electrodesal_tea_li.model.compute_lcol`.

    Raises
    ------
    FileNotFoundError
        If *config_path* cannot be found.
    """
    if config_path is None:
        config_path = Path(__file__).parent.parent / "config.yaml"
    config_path = Path(config_path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with config_path.open() as fh:
        params = yaml.safe_load(fh)

    return params


def sensitivity_ranges() -> dict:
    """
    Return the default one-at-a-time sensitivity analysis parameter ranges.

    Returns
    -------
    dict
        Keys are parameter names; values are ``[min, max]`` two-element lists.
    """
    return {
        "r":           [0.50, 0.95],   # water recovery
        "r_e":         [0.00, 0.80],   # energy recovery
        "c_in":        [50,   500],    # feed Li concentration [mg/L]
        "C_IEM":       [1,    200],    # IEM cost [$/m²]
        "C_car":       [1,    50],     # activated carbon cost [$/kg]
        "VC_electri":  [0.02, 0.21],   # electricity price [$/kWh]
        "L_elec":      [0.001, 100],   # electrode lifespan [years]
        "ALAR":        [1,    10],     # Li adsorption rate [mg/g/h]
        "SEC":         [0.1,  1000],   # specific energy [kWh/kg Li]
        "Thk_elec":    [0.1,  0.9],    # electrode thickness [mm]
        "r_extr":      [0.001, 1.0],   # extraction efficiency
    }
