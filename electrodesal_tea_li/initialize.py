"""
initialize.py
-------------
Load model parameters from a YAML configuration file.

All baseline values are defined in ``config.yaml`` at the repo root.
The :func:`sensitivity_ranges` function returns the one-at-a-time (OAT)
parameter sweep bounds used by the sensitivity analysis scripts.

Since the hybrid LFP/AC electrode costing update, ``config.yaml`` must
also define ``C_LFP`` (LFP material cost, $/kg) and ``Rm`` (AC:LFP
electrode mass ratio, ``M_AC / M_LFP``). :func:`load_params` checks for
these explicitly so a missing key fails clearly here rather than as a
``KeyError`` deep inside :func:`~electrodesal_tea_li.model.compute_lcol`.
"""

from __future__ import annotations

from pathlib import Path

import yaml

# New keys required since the hybrid LFP/AC costing update. Checked
# explicitly in load_params() so an out-of-date config.yaml fails with
# a clear, actionable message instead of a bare KeyError in compute_lcol.
_NEW_REQUIRED_KEYS: dict[str, str] = {
    "C_LFP": "LFP material cost [$/kg] -- priced separately from activated carbon",
    "Rm": "AC:LFP electrode mass ratio, M_AC / M_LFP -- start with Rm: 1",
}


def load_params(
    config_path: str | Path | None = None,
    overrides: dict | None = None,
) -> dict:
    """
    Load and return the baseline parameter dictionary from *config_path*.

    Parameters
    ----------
    config_path : str or Path, optional
        Path to the YAML configuration file.  Defaults to
        ``config.yaml`` two levels above this module (repo root).
    overrides : dict, optional
        Values to merge in on top of the loaded YAML *before* the
        required-key check below runs. ``None`` values in *overrides*
        are ignored (so callers can pass e.g. ``{"Rm": args.rm}``
        unconditionally, whether or not ``--rm`` was actually supplied).
        This lets a CLI flag such as ``--rm`` satisfy the ``Rm``
        requirement even when it is absent from ``config.yaml`` itself.

    Returns
    -------
    dict
        Parameter dictionary ready for :func:`~electrodesal_tea_li.model.compute_lcol`.

    Raises
    ------
    FileNotFoundError
        If *config_path* cannot be found.
    KeyError
        If, after applying *overrides*, ``C_LFP`` or ``Rm`` are still
        missing.
    """
    if config_path is None:
        config_path = Path(__file__).parent.parent / "config.yaml"
    config_path = Path(config_path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with config_path.open() as fh:
        params = yaml.safe_load(fh)

    if overrides:
        params.update({k: v for k, v in overrides.items() if v is not None})

    missing = [k for k in _NEW_REQUIRED_KEYS if k not in params]
    if missing:
        hints = "\n".join(f"  - {k}: {_NEW_REQUIRED_KEYS[k]}" for k in missing)
        raise KeyError(
            f"{config_path} is missing key(s) required for hybrid LFP/AC "
            f"electrode costing (and no override was supplied for them):\n{hints}"
        )

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
        "C_LFP":       [10,   30],     # LFP cost [$/kg]
        "Rm":          [0.2,  5.0],    # AC:LFP electrode mass ratio (M_AC/M_LFP)
        "VC_electri":  [0.02, 0.21],   # electricity price [$/kWh]
        "L_elec":      [0.001, 100],   # electrode lifespan [years]
        "ALAR":        [1,    10],     # Li adsorption rate [mg/g/h]
        "SEC":         [0.1,  1000],   # specific energy [kWh/kg Li]
        "Thk_elec":    [0.1,  0.9],    # electrode thickness [mm]
        "r_extr":      [0.001, 1.0],   # extraction efficiency
    }