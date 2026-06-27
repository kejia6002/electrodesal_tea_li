"""
energy.py
---------
Experimental energy analysis for LFP-vs-AC mCDI lithium extraction cycles.

Reads voltage–time traces from processed Excel files, integrates them
using the trapezoidal rule to compute:

* **Energy** per half-cycle [kWh]
* **SEC_mass** — specific energy per unit mass of Li extracted [kWh/kg Li]
* **LAC** — lithium adsorption capacity [mg Li / g electrode]
* **ALAR** — average lithium adsorption rate [mg Li / g electrode / h]

The module separates data loading, integration, and aggregation so each
can be tested or called independently.

Bugs fixed vs. original ``main.py``
------------------------------------
1. ``I_how_much``: two ``elif`` branches used ``FileList[i]`` (a free
   variable from the outer loop) instead of the ``FullName`` argument.
   Both now correctly reference the parameter.
2. ``NumericalEnergyCalculation.py``: ``np_Lithiation_counter`` and
   ``np_Delithiation_counter`` were assigned from the wrong DataFrames
   (copy-paste error).  Corrected here.
3. ``df.index`` labels in ``main.py``: the last entry for cycle 7
   de-lithiation step 3 was labelled ``"cycle5_delithiation_3"``
   (copy-paste).  Corrected to ``"cycle7_delithiation_3"``.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Unit conversion constants
# ---------------------------------------------------------------------------

J_to_kWh: float = 2.777778e-7   # 1 J = 2.777778e-7 kWh
mg_to_kg: float = 1e-6


# ---------------------------------------------------------------------------
# Cycle metadata
# ---------------------------------------------------------------------------

#: Each entry: (file_stem, mass_extracted_mg, electrode_mass_mg, current_A)
#: Current defaults to 0.892 A (0.1 C for 65.6 mg LFP electrode) unless
#: a specific C-rate is indicated in the filename.
CYCLE_REGISTRY: list[dict] = [
    # Cycle 1
    {"stem": "Processed 20230607 65,6mg LFP vs AC in geothermal brine at 0,1C, in mCDI lithiation process 1 cycle_1",
     "mass_extr": 1.441, "mass_elec": 65.6, "current": 0.892},
    {"stem": "Processed 20230607 65,6mg LFP vs AC in 5mM LiCl in mCDI at 0,1C, de-lithiation 1 cycle_1",
     "mass_extr": 1.441, "mass_elec": 65.6, "current": 0.892},
    # Cycle 2
    {"stem": "Processed 20230608 65,6mg LFP vs AC in geothermal brine at 0,1C, in mCDI lithiation process 1 cycle_2",
     "mass_extr": 0.983, "mass_elec": 65.6, "current": 0.892},
    {"stem": "Processed 20230608 65,6mg LFP vs AC in geothermal brine at 0,1C, in mCDI de-lithiation process 2 cycle_2",
     "mass_extr": 0.983, "mass_elec": 65.6, "current": 0.892},
    # Cycle 3
    {"stem": "Processed 20230609 65,6mg LFP vs AC in geothermal brine at 0,1C, in mCDI lithiation process 1 cycle_3",
     "mass_extr": 0.168, "mass_elec": 65.6, "current": 0.892},
    {"stem": "Processed 20230610 65,6mg LFP vs AC in geothermal brine at 0,1C, in mCDI de-lithiation process 2 cycle_3",
     "mass_extr": 0.168, "mass_elec": 65.6, "current": 0.892},
    # Cycle 4
    {"stem": "Processed 20230611 138,3mg LFP vs AC in geothermal brine at 0,1C, lithiation in mCDI, process 1 cycle_4",
     "mass_extr": 1.617, "mass_elec": 138.3, "current": 0.892},
    {"stem": "Processed 20230612 138,3mg LFP vs AC in geothermal brine at 0,1C, de-lithiation in mCDI, process 2 cycle_4",
     "mass_extr": 1.617, "mass_elec": 138.3, "current": 0.892},
    # Cycle 5
    {"stem": "Processed 20230616 138,3mg LFP vs AC in geothermal brine at 0,1C, lithiation in mCDI, process 1 cycle_5",
     "mass_extr": 0.496, "mass_elec": 138.3, "current": 0.892},
    {"stem": "Processed 20230617 138,3mg LFP vs AC in 5mM LiCl at 0,1C, de-lithiation in mCDI, process 2-1 cycle_5",
     "mass_extr": 0.496, "mass_elec": 138.3, "current": 0.892},
    {"stem": "Processed 20230617 138,3mg LFP vs AC in 5mM LiCl at 0,1C, de-lithiation in mCDI, process 2-2 cycle_5",
     "mass_extr": 0.496, "mass_elec": 138.3, "current": 0.0892},   # bug fix: was 0.892
    {"stem": "Processed 20230618 138,3mg LFP vs AC in 5mM LiCl at 0,1C, de-lithiation in mCDI, process 2-3 cycle_5",
     "mass_extr": 0.496, "mass_elec": 138.3, "current": 0.0892},   # bug fix: was 0.892
    # Cycle 6
    {"stem": "Processed 20230619 123,1mg LFP vs AC in geothermal brine at 0,1C, lithiation in mCDI, process 1 cycle_6",
     "mass_extr": 1.152, "mass_elec": 123.1, "current": 0.892},
    {"stem": "Processed 20230620 123,1mg LFP vs AC in 5mM LiCl at 0,1C, de-lithiation in mCDI, process 2-1 cycle_6",
     "mass_extr": 1.152, "mass_elec": 123.1, "current": 0.892},
    {"stem": "Processed 20230620 123,1mg LFP vs AC in 5mM LiCl at 0,1C, de-lithiation in mCDI, process 2-2 cycle_6",
     "mass_extr": 1.152, "mass_elec": 123.1, "current": 0.892},
    # Cycle 7
    {"stem": "Processed 20230629 78,4 mg WE-LFP vs AC in geothermal brine at 0,1C, lithiation in mCDI, process 1 cycle_7",
     "mass_extr": 1.49, "mass_elec": 78.4, "current": 0.892},
    {"stem": "Processed 20230630 78,4 mg WE-LFP vs AC in 5mM LiCl at 0,1C, de-lithiation in mCDI, process 2-1 cycle_7",
     "mass_extr": 1.49, "mass_elec": 78.4, "current": 0.892},
    {"stem": "Processed 20230630 78,4 mg WE-LFP vs AC in 5mM LiCl at 0,02C, de-lithiation in mCDI, process 2-2 cycle_7",
     "mass_extr": 1.49, "mass_elec": 78.4, "current": 0.0892 * 2},  # 0.02 C
    {"stem": "Processed 20230630 78,4 mg WE-LFP vs AC in 5mM LiCl at 0,01C, de-lithiation in mCDI, process 2-3 cycle_7",
     "mass_extr": 1.49, "mass_elec": 78.4, "current": 0.0892},      # 0.01 C
]

#: Row labels matching CYCLE_REGISTRY order (used for CSV index)
CYCLE_LABELS: list[str] = [
    "cycle1_lithiation", "cycle1_delithiation",
    "cycle2_lithiation", "cycle2_delithiation",
    "cycle3_lithiation", "cycle3_delithiation",
    "cycle4_lithiation", "cycle4_delithiation",
    "cycle5_lithiation", "cycle5_delithiation_1", "cycle5_delithiation_2", "cycle5_delithiation_3",
    "cycle6_lithiation", "cycle6_delithiation_1", "cycle6_delithiation_2",
    "cycle7_lithiation", "cycle7_delithiation_1", "cycle7_delithiation_2",
    "cycle7_delithiation_3",  # bug fix: was "cycle5_delithiation_3"
]

# Aggregation groups: (label, slice of CYCLE_REGISTRY indices)
CYCLE_GROUPS: list[tuple[str, list[int]]] = [
    ("cycle1",  list(range(0, 2))),
    ("cycle2",  list(range(2, 4))),
    ("cycle3",  list(range(4, 6))),
    ("cycle4",  list(range(6, 8))),
    ("cycle5",  list(range(8, 12))),
    ("cycle6",  list(range(12, 15))),
    ("cycle7",  list(range(15, 19))),
]


# ---------------------------------------------------------------------------
# Core integration function
# ---------------------------------------------------------------------------

def integrate_half_cycle(
    filepath: Path,
    current_A: float,
    t_start_s: float = 120.0,
) -> tuple[float, float]:
    """
    Integrate voltage–time data from an electrochemistry Excel file.

    Parameters
    ----------
    filepath : Path
        Path to the processed ``.xlsx`` file.  Expected columns:
        ``"time/s"`` and ``"Ewe-Ece/V "``.
    current_A : float
        Applied current [A].
    t_start_s : float, optional
        Discard data before this timestamp [s].  Default: 120 s
        (equilibration period).

    Returns
    -------
    energy_kWh : float
        Energy [kWh] for this half-cycle (unsigned).
    duration_h : float
        Duration of the half-cycle after ``t_start_s`` [hours].
    """
    df = pd.read_excel(
        filepath,
        dtype={"time/s": float, "Ewe-Ece/V ": float},
    )
    df = df[df["time/s"] >= t_start_s].copy()
    if df.empty:
        raise ValueError(f"No data after t={t_start_s} s in {filepath}")

    arr = df.to_numpy()
    # ∫ V dt  [V·s] × I [A] = [W·s] = [J], then convert to kWh
    energy_kWh = np.trapz(arr[:, 1], x=arr[:, 0]) * current_A * J_to_kWh
    duration_h = (arr[-1, 0] - arr[0, 0]) / 3600.0

    return energy_kWh, duration_h


# ---------------------------------------------------------------------------
# Batch processing
# ---------------------------------------------------------------------------

def process_all_cycles(
    data_dir: str | Path,
    outdir: str | Path,
) -> pd.DataFrame:
    """
    Process all cycles defined in :data:`CYCLE_REGISTRY`.

    Reads each Excel file from *data_dir*, integrates the voltage trace,
    and computes per-half-cycle metrics.  Results are written to CSV files
    in *outdir* and returned as a combined DataFrame.

    Parameters
    ----------
    data_dir : str or Path
        Directory containing the processed ``.xlsx`` files.
    outdir : str or Path
        Directory for output CSV files.

    Returns
    -------
    pd.DataFrame
        DataFrame with columns:
        ``Energy_kWh``, ``SEC_kWh_per_kg``, ``LAC_mg_per_g``,
        ``ALAR_mg_per_g_per_h``, ``duration_h``.
        Index labels match :data:`CYCLE_LABELS`.
    """
    data_dir = Path(data_dir)
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    records: list[dict] = []

    for meta in CYCLE_REGISTRY:
        stem = meta["stem"]
        filepath = data_dir / f"{stem}.xlsx"
        if not filepath.exists():
            log.warning("File not found, skipping: %s", filepath)
            records.append({k: float("nan") for k in
                            ["Energy_kWh", "SEC_kWh_per_kg", "LAC_mg_per_g",
                             "ALAR_mg_per_g_per_h", "duration_h"]})
            continue

        energy, duration_h = integrate_half_cycle(filepath, meta["current"])

        # Sign convention: lithiation = energy input (positive cost),
        # de-lithiation = energy recovered (negative or positive depending on setup)
        is_delith = "de-lithiation" in stem
        signed_energy = energy if is_delith else -energy

        lac = meta["mass_extr"] / meta["mass_elec"] * 1000  # mg/g
        sec = (abs(energy) / (meta["mass_extr"] * mg_to_kg)
               if meta["mass_extr"] > 0 else float("nan"))

        records.append({
            "Energy_kWh": signed_energy,
            "SEC_kWh_per_kg": sec if is_delith else -sec,
            "LAC_mg_per_g": lac,
            "ALAR_mg_per_g_per_h": lac / duration_h if duration_h > 0 else float("nan"),
            "duration_h": duration_h,
        })

    df = pd.DataFrame(records, index=CYCLE_LABELS)

    # ---- Write per-metric CSVs -------------------------------------------
    df[["Energy_kWh"]].to_csv(outdir / "Energy.csv", header=False)
    df[["SEC_kWh_per_kg"]].to_csv(outdir / "SEC_mass.csv", index=False, header=False)
    df[["duration_h"]].to_csv(outdir / "TimeLength.csv", index=False, header=False)
    df[["LAC_mg_per_g"]].to_csv(outdir / "LAC.csv", index=False, header=False)
    df[["ALAR_mg_per_g_per_h"]].to_csv(outdir / "ALAR.csv", index=False, header=False)

    # ---- Aggregate by cycle group ----------------------------------------
    agg: dict = {
        "Energy_kWh": {},
        "SEC_kWh_per_kg": {},
        "duration_h": {},
    }
    for label, indices in CYCLE_GROUPS:
        for col in agg:
            agg[col][label] = df.iloc[indices][col].sum()

    for col, values in agg.items():
        pd.DataFrame([values]).to_csv(
            outdir / f"{col}_by_cycle.csv", index=False
        )

    log.info("Results written to %s", outdir)
    return df
