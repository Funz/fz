# fz-Simulate

[fz](https://github.com/Funz/fz) wrapper for Studsvik **SIMULATE** (core simulator) and
for the full **CASMO5 → CMS-LINK → SIMULATE** chain, so that lattice *and* core
parameters can be varied in one parametric study, run locally, over SSH or on SLURM.

Two models:

| Model | Input | What a case runs |
|---|---|---|
| `Simulate` | one SIMULATE deck (+ library) | SIMULATE |
| `CasmoSimulate` | a case directory (see below) | every CASMO deck, then CMS-LINK, then SIMULATE |

CASMO alone is covered by [fz-Casmo](https://github.com/Funz/fz-Casmo).

## Requirements

- fz > 1.2 (installing both models of this repository needs the fix installing every
  `.fz/models/*.json`; with fz 1.2 only one model gets installed, copy the other one
  from `.fz/models/` by hand)
- licensed Studsvik codes, each located by (first match wins) `*_CMD` (full command),
  `*_PATH` (install dir, launcher in it or in `bin/`), or the launcher name on `PATH`:

| Code | Command | Install dir | Launcher names tried | Options |
|---|---|---|---|---|
| CASMO5 | `CASMO_CMD` | `CASMO_PATH` | `cas5` | `CASMO_OPTS` (default `-p -k`) |
| CMS-LINK | `CMSLINK_CMD` | `CMSLINK_PATH` | `cmslink5`, `cmslink`, `link5` | `CMSLINK_OPTS` |
| SIMULATE | `SIMULATE_CMD` | `SIMULATE_PATH` | `sim5`, `simulate5`, `simulate3`, `s3` | `SIMULATE_OPTS` |

The launcher names are defaults to be checked against your installation; setting the
`*_CMD` variables avoids any guessing.

## Quick start

```bash
fz install model Simulate
export CASMO_CMD=/opt/studsvik/bin/cas5 CMSLINK_CMD=... SIMULATE_CMD=...

# SIMULATE alone, library shared by all cases
fzr examples/Simulate/simulate.inp --model Simulate --input_static cms.lib \
    --input_variables '{"core_power": [100, 90, 80]}' --format json

# whole chain: vary a lattice parameter and a core parameter together
fzr examples/CasmoSimulate --model CasmoSimulate \
    --input_variables '{"enrichment_B": [4.2, 4.6, 4.95], "cycle_length": [16, 18]}' \
    --format json
```

```python
import fz
res = fz.fzr("examples/CasmoSimulate",
             {"enrichment_B": [4.2, 4.6, 4.95]},
             model="CasmoSimulate", results_dir="results")
print(res[["enrichment_B", "boron", "fdh", "status"]])
```

## Chain case layout (`CasmoSimulate`)

```
examples/CasmoSimulate/
├── casmo/fuel_A.inp     CASMO deck per segment (any number of *.inp)
├── casmo/fuel_B.inp
├── cmslink.inp          CMS-LINK deck: reads casmo/*.cax, writes the library
└── simulate.inp         SIMULATE deck: reads that library
```

Per case, the runner (`.fz/calculators/CasmoSimulate.sh`):

1. runs every `casmo/*.inp` (`CASMO_JOBS` at a time, default 1) and checks each produced
   its `.out` and `.cax` (log: `casmo/<deck>.log`);
2. runs CMS-LINK on `cmslink.inp`;
3. runs SIMULATE on `simulate.inp`.

A failed stage stops the chain; the exit status says where: 2 setup, 10 CASMO, 20
CMS-LINK, 30/31 SIMULATE. The file names can be changed with `CHAIN_CASMO_DIR`,
`CHAIN_CMSLINK_INPUT`, `CHAIN_SIMULATE_INPUT`. The chain model has a 4 h timeout per case
(`"timeout"` in `.fz/models/CasmoSimulate.json`).

Variables may appear in any file of the tree; `fzi` lists them all, and one fz case
compiles all files with the same values. Lattice calculations are redone for every
case: for studies that vary only core parameters, run the chain once and use the
`Simulate` model with the resulting library as `--input_static`.

## Input syntax

Same for both models and all decks: `${name}` / `${name~default}` variables,
`@{expr}` Python formulas, `*@` formula context lines, `*` comments.

The example decks are **skeletons**: they show the parameterization, not a complete
core model. Replace their content with the decks of your methodology (core loading,
geometry, CASMO branch cases for CMS-LINK), keeping the fz variables where needed.

## Outputs

Parsed from the SIMULATE output (first `*.out` of the case directory not named
`cmslink*`), one value per state/depletion step:

| Output | Content |
|---|---|
| `keff` | k-effective |
| `boron` | boron concentration [ppm] |
| `cycle_exposure` | cycle exposure |
| `fq`, `fdh` | peaking factors |
| `axial_offset` | axial offset [%] |
| `n_steps` | number of steps found |
| `casmo_decks`, `cax_files` | (chain only) CASMO decks run, `.cax` files produced |

**Validation status:** these parsers are provisional. They were written for the
summary lines of a SIMULATE-3 style output (`K-effective . . . 1.00000`,
`Boron Conc. . . . 1234.5 ppm`, ...) and have not yet been checked against real
SIMULATE outputs. Add real excerpts in `tests/fixtures/` (below) and adjust the
regular expressions of `.fz/models/*.json` until the tests pass.

## Tests

```bash
pip install funz-fz pytest
pytest tests/
```

No Studsvik code is needed: `tests/mock/{cas5,cmslink,sim5}` are fake launchers that
carry data along the chain (CASMO k-inf → library → SIMULATE boron), so the tests
check that a parameter of a CASMO deck really reaches the SIMULATE result, plus alias
discovery, `--input_static` handling, parallel CASMO runs and failure reporting.

Every `tests/fixtures/<case>/` holding an `expected.json` is parsed with `fzo` and
compared with it: this is where real SIMULATE outputs go to validate the parsers.
`tests/fixtures/synthetic_cycle/` is hand-written, not a SIMULATE output.

## Remote execution

Add an alias next to `localhost_Simulate.json`, with the scripts installed on the
remote side (`Simulate.sh`/`CasmoSimulate.sh` need `cms_common.sh` in the same
directory):

```json
{ "uri": "slurm://user@cluster:batch",
  "models": { "CasmoSimulate": "bash /path/to/CasmoSimulate.sh" } }
```

## License

BSD 3-Clause License. See [LICENSE](LICENSE).
