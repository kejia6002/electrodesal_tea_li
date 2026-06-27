# ElectroDesal-TEA (Lithium): Techno-Economic Model for mCDI Lithium Extraction

A Python model for computing the **Levelised Cost of Lithium (LCOL, $/kg LiOH·H₂O)**
for membrane capacitive deionisation (mCDI) applied to lithium recovery from
geothermal brines.  Also includes experimental energy analysis utilities for
processing raw LFP-vs-AC half-cell cycling data.

---

## Model overview

The LCOL model follows a bottom-up TEA framework:

```
LCOL = CAPEX contribution + OPEX contribution
```

**CAPEX** components:
- Electrode materials (activated carbon + carbon black + PTFE binder)
- Ion exchange membranes (IEM)
- Current collectors, spacers, and module housing
- Balance of system (pumps, sensors, electronic controls)
- Indirect costs (engineering, contingency)

**OPEX** components:
- Electricity (electrochemical + pumping + wash water)
- Periodic electrode replacement
- Periodic IEM replacement
- Maintenance, labor, and chemicals

System sizing is derived from the electrode-level Average Lithium Adsorption
Rate (ALAR, mg/g/h) and specific energy consumption (SEC, kWh/kg Li).

---

## Repository structure

```
electrodesal_tea_li/
├── electrodesal_tea_li/
│   ├── __init__.py        # Public API
│   ├── initialize.py      # Parameter loading (YAML config)
│   ├── model.py           # Core LCOL calculation (LCOLResult)
│   ├── energy.py          # Experimental energy analysis from Excel files
│   └── sensitivity.py     # One-at-a-time sensitivity analysis
├── tests/
│   └── __init__.py
├── data/
│   ├── raw/               # Raw .xlsx electrochemistry files (not tracked)
│   └── processed/         # Processed experimental outputs (not tracked)
├── results/               # Model output CSVs (git-ignored by default)
├── config.yaml            # Baseline parameters (edit to customise)
├── run_model.py           # CLI entry point for the LCOL model
└── requirements.txt
```

---

## Installation

```bash
git clone https://github.com/<your-org>/electrodesal-tea-li.git
cd electrodesal-tea-li
pip install -r requirements.txt
```

No package installation is required; the model runs directly from the
repo root.

---

## Quick start

**Run the baseline LCOL model:**

```bash
python run_model.py
```

**Custom config and output directory:**

```bash
python run_model.py --config my_config.yaml --outdir /path/to/output
```

**Run sensitivity analysis:**

```bash
python -m electrodesal_tea_li.sensitivity --outdir results/sensitivity
```

**Process experimental cycling data:**

```python
from electrodesal_tea_li import process_all_cycles

df = process_all_cycles(
    data_dir="data/raw",
    outdir="results/experimental",
)
print(df)
```

**Use the LCOL model as a library:**

```python
from electrodesal_tea_li import load_params, compute_lcol

params = load_params()
result = compute_lcol(params)
print(f"LCOL  = {result.LCOL:.2f}  $/kg LiOH·H₂O")
print(f"CAPEX = {result.LCOL_CC:.2f}  $/kg LiOH·H₂O")
print(f"OPEX  = {result.LCOL_OC:.2f}  $/kg LiOH·H₂O")
```

---

## Configuration

All baseline parameters are defined in [`config.yaml`](config.yaml).
Key parameters:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `c_in` | 232 mg/L | Feed lithium concentration |
| `Q_out` | 100,000 gpd | Product flow rate |
| `r` | 0.8 | Water recovery |
| `ALAR` | 1.373 mg/g/h | Average Li adsorption rate |
| `SEC` | 5.0 kWh/kg | Specific energy consumption |
| `r_extr` | 0.18 | Lithium extraction efficiency |
| `C_IEM` | 60 $/m² | IEM areal cost |
| `VC_electri` | 0.07 $/kWh | Electricity price |
| `i` | 0.07 | Discount rate |
| `L_pl` | 20 years | Plant service life |

---

## Sensitivity analysis

The OAT sensitivity analysis sweeps 11 parameters independently:

| Parameter | Range | Notes |
|-----------|-------|-------|
| `r` | 50–95% | Water recovery |
| `r_e` | 0–80% | Energy recovery |
| `c_in` | 50–500 mg/L | Feed Li concentration |
| `C_IEM` | 1–200 $/m² | IEM cost |
| `C_car` | 1–50 $/kg | Carbon cost |
| `VC_electri` | 0.02–0.21 $/kWh | Electricity price |
| `L_elec` | 0.001–100 yr | Electrode lifespan (log sweep) |
| `ALAR` | 1–10 mg/g/h | Adsorption rate |
| `SEC` | 0.1–1000 kWh/kg | Specific energy |
| `Thk_elec` | 0.1–0.9 mm | Electrode thickness |
| `r_extr` | 0.1–100% | Extraction efficiency (log sweep) |

---

## Output files

| File | Contents |
|------|----------|
| `results/MCDI-baseline_LCOL.csv` | Total LCOL and nine-bucket summary |
| `results/MCDI-baseline_LCOL_Breakdown.csv` | Full CAPEX + OPEX component table |
| `results/sensitivity/MCDI-baseline_<param>.csv` | Per-parameter sensitivity sweep |
| `results/experimental/Energy.csv` | Per-half-cycle energy [kWh] |
| `results/experimental/LAC.csv` | Li adsorption capacity [mg/g] |
| `results/experimental/ALAR.csv` | Average adsorption rate [mg/g/h] |

---

## Known issues and corrections

The following bugs were identified and fixed during repo preparation:

1. **`main.py` — `I_how_much` scoping bug**: two `elif` branches used
   `FileList[i]` (a loop variable from the enclosing scope) instead of
   the `FullName` parameter.  Both branches now correctly reference
   `FullName`.

2. **`NumericalEnergyCalculation.py` — copy-paste error**: `np_Lithiation_counter`
   and `np_Delithiation_counter` were assigned from the wrong DataFrames.
   Corrected in `energy.py`.

3. **`main.py` — mislabelled cycle index**: the last entry in cycle 7
   de-lithiation step 3 was labelled `"cycle5_delithiation_3"`.
   Corrected to `"cycle7_delithiation_3"`.

4. **`sim_sens_breakdown_revised.py` — naming inconsistency**: the script
   used `LCOW` variable names while the model returned `LCOL`.
   All references are now consistently `LCOL`.

---

## Citation

If you use this model in published work, please cite the associated
thesis or paper (update this section with your reference):

> [Author]. *Techno-Economic Analysis of mCDI for Lithium Extraction
> from Geothermal Brines*. [Journal/Thesis], [Year].

---

## License

[MIT](LICENSE)
