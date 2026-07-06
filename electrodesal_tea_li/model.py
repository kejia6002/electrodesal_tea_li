"""
model.py
--------
Core techno-economic model for mCDI-based lithium extraction.

Computes the Levelised Cost of Lithium (LCOL, $/kg LiOH·H₂O) from
first principles, decomposing total cost into capital (CAPEX) and
operational (OPEX) components.

Main entry point: :func:`compute_lcol`.

References
----------
- van der Wal et al., Environ. Sci. Technol. 2013, 47, 4904–4910
  (energy recovery for MCDI).
- Straub & Elimelech, Environ. Sci. Technol. 2014 (specific pumping energy).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# Electrode composite recipe (active material : carbon black : PTFE mass
# ratio), per Methods: 80:10:10 -- used identically on both the LFP side
# (active material = LFP) and the AC side (active material = activated
# carbon). Named here so the same recipe assumption is used consistently
# for electrode CAPEX (blended $/kg price) and for converting the
# ALAR-derived *pure* LFP mass demand into an LFP-side *composite* mass
# for stack counting -- see M_stack_pure_LFP below.
COMPOSITE_ACTIVE_FRAC = 0.80
COMPOSITE_CB_FRAC = 0.10
COMPOSITE_PTFE_FRAC = 0.10


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------

@dataclass
class LCOLResult:
    """
    All cost components returned by :func:`compute_lcol`.

    All monetary values are in **$/kg LiOH·H₂O** unless otherwise noted.
    """

    # --- Totals ---
    LCOL: float = 0.0       # Total levelised cost of lithium [$/kg LiOH·H₂O]
    LCOL_CC: float = 0.0    # Total CAPEX contribution
    LCOL_OC: float = 0.0    # Total OPEX contribution

    # --- CAPEX breakdown ---
    LCOL_CC_elec: float = 0.0       # Electrode capital cost (LFP side + AC side)
    LCOL_CC_elec_LFP: float = 0.0   # Electrode capital cost, LFP side only
    LCOL_CC_elec_AC: float = 0.0    # Electrode capital cost, AC side only
    LCOL_CC_IEM: float = 0.0        # Ion exchange membrane capital cost
    LCOL_CC_cc_sp_H: float = 0.0    # Current collectors, spacers, housing
    LCOL_CC_BOS: float = 0.0        # Balance of system
    LCOL_CC_indirect: float = 0.0   # Indirect costs

    # --- OPEX breakdown ---
    LCOL_OC_electricity: float = 0.0      # Electricity cost
    LCOL_OC_replace_elec: float = 0.0    # Electrode replacement (LFP + AC)
    LCOL_OC_replace_IEM: float = 0.0     # IEM replacement
    LCOL_OC_replace_cc_sp_H: float = 0.0  # CC/spacer/housing replacement
    LCOL_OC_MLC: float = 0.0             # Maintenance, labor, chemicals

    # --- Diagnostic outputs ---
    SEC: float = 0.0         # Specific energy consumption passed through [kWh/kg Li]
    n_stack: int = 0         # Total stacks
    n_module: int = 0        # Total modules
    M_elec: float = 0.0      # Pure LFP mass needed, sized from ALAR [kg]
    M_stack_elec: float = 0.0    # Total electrode mass per stack, LFP+AC combined [kg]
    M_stack_elec_LFP: float = 0.0  # LFP-side composite electrode mass per stack [kg]
    M_stack_elec_AC: float = 0.0   # AC-side composite electrode mass per stack [kg]
    M_stack_pure_LFP: float = 0.0  # Pure (active-material-only) LFP mass per stack [kg]
    Rm: float = 0.0           # AC:LFP electrode mass ratio actually used
    LiOH_mass_year: float = 0.0  # LiOH·H₂O production [kg/year]

    def capex_breakdown(self) -> dict:
        """Return CAPEX components as a labelled dictionary."""
        return {
            "Electrode (LFP)":   self.LCOL_CC_elec_LFP,
            "Electrode (AC)":    self.LCOL_CC_elec_AC,
            "IEM":               self.LCOL_CC_IEM,
            "CC/Spacer/Housing": self.LCOL_CC_cc_sp_H,
            "Balance of System": self.LCOL_CC_BOS,
            "Indirect":          self.LCOL_CC_indirect,
        }

    def opex_breakdown(self) -> dict:
        """Return OPEX components as a labelled dictionary."""
        return {
            "Electricity":              self.LCOL_OC_electricity,
            "Electrode Replacement":    self.LCOL_OC_replace_elec,
            "IEM Replacement":          self.LCOL_OC_replace_IEM,
            "CC/Spacer/Housing Replace": self.LCOL_OC_replace_cc_sp_H,
            "Maintenance/Labor/Chem":   self.LCOL_OC_MLC,
        }

    def summary_breakdown(self) -> dict:
        """
        Compact five-bucket breakdown suitable for stacked bar charts.
        Matches the original ``Cost_case`` CSV output structure.
        """
        return {
            "LCOL":              self.LCOL,
            "LCOL_CapEx":        self.LCOL_CC,
            "LCOL_OpEx":         self.LCOL_OC,
            "SEC":               self.SEC,
            "LCOL_Electrode":    self.LCOL_CC_elec + self.LCOL_OC_replace_elec,
            "LCOL_IEM":          self.LCOL_CC_IEM + self.LCOL_OC_replace_IEM,
            "LCOL_OtherCapEx":   self.LCOL_CC_cc_sp_H + self.LCOL_CC_BOS + self.LCOL_CC_indirect,
            "LCOL_Electricity":  self.LCOL_OC_electricity,
            "LCOL_OtherOpEx":    self.LCOL_OC_replace_cc_sp_H + self.LCOL_OC_MLC,
        }


# ---------------------------------------------------------------------------
# Core model
# ---------------------------------------------------------------------------

def compute_lcol(params: dict) -> LCOLResult:
    """
    Compute the Levelised Cost of Lithium for an mCDI extraction system.

    Parameters
    ----------
    params : dict
        Parameter dictionary from :func:`~electrodesal_tea_li.initialize.load_params`.
        All keys are documented in ``config.yaml``. Must now also include:

        ``C_LFP``
            LFP material cost [$/kg], costed separately from activated carbon.
        ``Rm``
            Mass ratio of the AC (counter) electrode to the LFP (working)
            electrode, ``Rm = M_AC / M_LFP``, within a single cell pair.
            ``Rm = 1`` means the two electrodes have equal mass (the
            default/starting assumption, pending confirmed fabrication data
            for the AC side). ``Rm < 1`` means AC is lighter than LFP;
            ``Rm > 1`` means AC is heavier.

    Returns
    -------
    LCOLResult
        Fully populated result dataclass with all cost components and
        system-sizing outputs.

    Notes
    -----
    **Product basis**: costs are expressed per kg of LiOH·H₂O
    (molar mass 41.96 g/mol), converted from kg Li extracted using
    ``Li_MW`` and ``LiOH_MW`` from params.

    **Hybrid LFP/AC electrode costing**: the cell pairs an LFP working
    electrode with an activated-carbon (AC) counter electrode (see
    Methods). ``M_stack_elec`` (from stack geometry) is the *combined*
    mass of both electrode layers per stack; ``Rm`` splits this into an
    LFP-side share and an AC-side share, each costed with its own
    80:10:10 (active material : carbon black : PTFE) composite recipe
    and its own active-material price (``C_LFP`` vs. ``C_car``).

    **ALAR/M_elec basis and units**: ``ALAR`` (and hence ``M_elec``) is
    defined per gram of *active LFP material* (see LAC = α·Cin·Vexpr /
    M_LFP,expr in the paper's Methods), not per gram of the LFP-side
    composite electrode (which also contains carbon black and PTFE
    binder). ``M_elec`` converts ``Q_in`` from m³/day to L/day (×1000)
    to match ``c_in``'s mg/L basis before converting the resulting Li
    mass rate from g to kg (÷1000) -- these are two different unit
    conversions for two different steps and do not cancel each other;
    a version of this model that omitted the ×1000 step understated
    ``M_elec`` (and therefore ``n_stack`` and every cost that scales
    with it) by 1000x. This version relates the resulting ``M_elec``
    to the LFP-side share of ``M_stack_elec`` (``M_stack_elec_LFP``),
    then further applies ``COMPOSITE_ACTIVE_FRAC`` (0.80) to convert
    that LFP-side *composite* mass into the *pure* LFP mass actually
    available per stack (``M_stack_pure_LFP``), since only 80% of the
    composite is active material -- the rest is carbon black and PTFE
    binder, per the same recipe used for costing. ``n_stack`` is sized
    against ``M_stack_pure_LFP`` accordingly.

    **Wash water cost**: a fixed wash protocol (60 min at 5 mL/min per
    2 mg Li) is hardcoded here, consistent with the original model.
    This can be parameterised in a future version.
    """
    # ---- Flow rates -------------------------------------------------------
    Gallons_to_m3: float = 3.78541e-3
    Q_out_m3_day = params["Q_out"] * Gallons_to_m3
    Q_in_m3_day = Q_out_m3_day / params["r"]

    # ---- Annual lithium and LiOH production -------------------------------
    Li_mass_year = (
        params["c_in"] * Q_out_m3_day * 365 * params["r_extr"] / 1000
    )  # kg Li/year
    LiOH_mass_year = Li_mass_year / params["Li_MW"] * params["LiOH_MW"]

    # ---- Stack / module sizing --------------------------------------------
    # Pure LFP mass needed [kg], sized from ALAR kinetics (mg Li / g LFP / h)
    M_elec = (
        params["c_in"]
        * Q_in_m3_day
        * 1000                  # m³/day → L/day (to match c_in's mg/L basis)
        * params["r_extr"]
        / 24                    # h/day
        / params["ALAR"]        # mg/g/h  →  [g Li / g LFP / h]
        / params["LF"]
        * params["n_train"]
        / 1000                  # g → kg
    )

    # Cell-pair thickness [mm]: spacer + 2 electrodes + 2 Ti CC + 1 IEM
    h_cellpair_mm = (
        params["Thk_sp"]
        + 2 * params["Thk_elec"]
        + 2 * params["Thk_cc_Ti"]
        + params["Thk_IEM"]
    )
    # Active electrode area in one stack [m²]; factor 2 for anode+cathode faces
    A_stack = (
        params["h_s"] / (h_cellpair_mm / 1000)  # number of cell pairs
        * params["W_cc"] ** 2                    # m² per cell
        * 2
    )
    # Mass of electrode material per stack [kg] -- LFP side + AC side combined
    M_stack_elec = A_stack * params["Thk_elec"] * params["Den"]

    # Split the combined per-stack electrode mass between the LFP working
    # electrode and the AC counter electrode using Rm = M_AC / M_LFP.
    Rm = params["Rm"]
    M_stack_elec_LFP = M_stack_elec / (1 + Rm)
    M_stack_elec_AC = M_stack_elec * Rm / (1 + Rm)

    # M_elec is PURE LFP mass needed (ALAR is normalized to active LFP
    # mass, not the LFP-side composite -- see the note above). Only
    # COMPOSITE_ACTIVE_FRAC of the LFP-side composite mass per stack is
    # actually pure LFP; the rest is carbon black + PTFE binder from the
    # same recipe used for costing below.
    M_stack_pure_LFP = M_stack_elec_LFP * COMPOSITE_ACTIVE_FRAC
    n_stack = math.ceil(M_elec / M_stack_pure_LFP)
    n_module = math.ceil(n_stack / params["n_stack_module"])

    # ---- Stack capital costs (per stack, then scaled by n_stack) ----------
    # Each side uses the same active:carbon-black:PTFE composite recipe
    # (COMPOSITE_ACTIVE_FRAC etc., defined at module level), but the LFP
    # side prices its active material at C_LFP and the AC side at C_car.
    CC_elec_LFP = (
        M_stack_elec_LFP
        * (
            COMPOSITE_ACTIVE_FRAC * params["C_LFP"]
            + COMPOSITE_CB_FRAC * params["C_cb"]
            + COMPOSITE_PTFE_FRAC * params["C_ptfe"]
        )
        * n_stack
    )
    CC_elec_AC = (
        M_stack_elec_AC
        * (
            COMPOSITE_ACTIVE_FRAC * params["C_car"]
            + COMPOSITE_CB_FRAC * params["C_cb"]
            + COMPOSITE_PTFE_FRAC * params["C_ptfe"]
        )
        * n_stack
    )
    CC_elec = CC_elec_LFP + CC_elec_AC

    CC_cc = A_stack * params["C_cc_Ti"] * n_stack
    CC_sp = A_stack * 0.5 * params["C_sp"] * n_stack
    CC_IEM = A_stack * 0.5 * params["C_IEM"] * n_stack

    # Housing: cylindrical body + two end-plates + auxiliary fittings
    _r = params["D_s"] / 2
    CC_housing_per_stack = (
        params["C_box"] * params["h_s"] * math.pi * params["D_s"]
        + params["C_plate"] * 2 * math.pi * _r ** 2
        + params["C_sa"]
    )
    CC_cc_sp_H = (CC_cc + CC_sp + CC_housing_per_stack * n_stack)

    CC_module = CC_elec + CC_cc_sp_H + CC_IEM

    # ---- Balance-of-system costs ------------------------------------------
    # One rotary pump per module; cost via empirical correlation (inflation-adj.)
    Q_pump_per_module = Q_in_m3_day / params["LF"] / n_module
    C_pump_r = 1829 * math.exp(0.000474 * Q_pump_per_module) * 1.56
    CC_pump = n_module * C_pump_r

    # Two conductivity + two pressure sensors per module
    CC_sens = (params["C_condSens"] + params["C_pressSens"]) * n_module * 2

    CC_vp = params["F_vp"] * CC_module
    CC_ec = params["F_ec"] * CC_module + params["C_ERD"] * n_stack

    CC_BOS = CC_pump + CC_sens + CC_vp + CC_ec

    # ---- Total capital cost -----------------------------------------------
    CC_equip = CC_module + CC_BOS
    CC_indirect = (CC_equip - CC_IEM) * (params["F_TCC"] - 1)
    TCC = CC_equip + CC_indirect

    # Capital recovery factor
    i, L_pl = params["i"], params["L_pl"]
    CF = i * (1 + i) ** L_pl / ((1 + i) ** L_pl - 1)

    # ---- Operating costs --------------------------------------------------
    SEC = params["SEC"]  # kWh/kg Li

    EU_charging = Li_mass_year * SEC          # kWh/year
    EU_pumping = params["SPE"] * Q_in_m3_day * 365  # kWh/year
    OC_electricity = (EU_charging + EU_pumping) * params["VC_electri"]

    # Wash water cost: 60 min at 5 mL/min per 2 mg Li extracted
    _wash_time_min = 60
    _flowrate_mL_min = 0.005 * 1000        # mL/min (original was L/min → ml)
    _water_per_cycle_mL = _flowrate_mL_min * _wash_time_min
    _wash_ratio_L_per_g = (_water_per_cycle_mL / 1000) / 2  # L/g Li
    water_volume_m3_year = _wash_ratio_L_per_g * Li_mass_year * 1000 / 1000  # m³/year
    _water_price = 2.08   # $/m³
    OC_water = _water_price * water_volume_m3_year

    # Replacement costs
    RR_elec = 1.0 / params["L_elec"]
    RR_IEM = 1.0 / params["L_IEM"]
    RR_eff = max(RR_elec, RR_IEM)

    OC_replace_elec = RR_eff * CC_elec
    OC_replace_IEM = RR_eff * CC_IEM
    OC_replace_cc_sp_H = RR_eff * CC_cc_sp_H

    OC_MLC = (params["F_ML"] + params["F_C"]) * TCC

    # ---- Levelised costs ($/kg LiOH·H₂O) ---------------------------------
    def _lev(annual_cost: float) -> float:
        return annual_cost / LiOH_mass_year

    LCOL_CC_elec_LFP = _lev(CC_elec_LFP * CF)
    LCOL_CC_elec_AC = _lev(CC_elec_AC * CF)
    LCOL_CC_elec = LCOL_CC_elec_LFP + LCOL_CC_elec_AC
    LCOL_CC_IEM = _lev(CC_IEM * CF)
    LCOL_CC_cc_sp_H = _lev(CC_cc_sp_H * CF)
    LCOL_CC_BOS = _lev(CC_BOS * CF)
    LCOL_CC_indirect = _lev(CC_indirect * CF)
    LCOL_CC = LCOL_CC_elec + LCOL_CC_IEM + LCOL_CC_cc_sp_H + LCOL_CC_BOS + LCOL_CC_indirect

    LCOL_OC_electricity = _lev(OC_electricity + OC_water)
    LCOL_OC_replace_elec = _lev(OC_replace_elec)
    LCOL_OC_replace_IEM = _lev(OC_replace_IEM)
    LCOL_OC_replace_cc_sp_H = _lev(OC_replace_cc_sp_H)
    LCOL_OC_MLC = _lev(OC_MLC)
    LCOL_OC = (
        LCOL_OC_electricity
        + LCOL_OC_replace_elec
        + LCOL_OC_replace_IEM
        + LCOL_OC_replace_cc_sp_H
        + LCOL_OC_MLC
    )

    return LCOLResult(
        LCOL=LCOL_CC + LCOL_OC,
        LCOL_CC=LCOL_CC,
        LCOL_OC=LCOL_OC,
        LCOL_CC_elec=LCOL_CC_elec,
        LCOL_CC_elec_LFP=LCOL_CC_elec_LFP,
        LCOL_CC_elec_AC=LCOL_CC_elec_AC,
        LCOL_CC_IEM=LCOL_CC_IEM,
        LCOL_CC_cc_sp_H=LCOL_CC_cc_sp_H,
        LCOL_CC_BOS=LCOL_CC_BOS,
        LCOL_CC_indirect=LCOL_CC_indirect,
        LCOL_OC_electricity=LCOL_OC_electricity,
        LCOL_OC_replace_elec=LCOL_OC_replace_elec,
        LCOL_OC_replace_IEM=LCOL_OC_replace_IEM,
        LCOL_OC_replace_cc_sp_H=LCOL_OC_replace_cc_sp_H,
        LCOL_OC_MLC=LCOL_OC_MLC,
        SEC=SEC,
        n_stack=n_stack,
        n_module=n_module,
        M_elec=M_elec,
        M_stack_elec=M_stack_elec,
        M_stack_elec_LFP=M_stack_elec_LFP,
        M_stack_elec_AC=M_stack_elec_AC,
        M_stack_pure_LFP=M_stack_pure_LFP,
        Rm=Rm,
        LiOH_mass_year=LiOH_mass_year,
    )