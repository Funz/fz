# Installing Models and Algorithms

fz can install ready-made **models** (simulation-code wrappers) and **fzd algorithms**
(design-of-experiments / optimization strategies) from GitHub or local zip files, so you
don't have to author them by hand. This is the first thing to try when wrapping a known
code: an official wrapper may give you the parameterization syntax and output parsers for
free.

## CLI

```bash
# Install a model into the current project (./.fz/models/)
fz install model perfectgas
fz install model https://github.com/Funz/fz-modelica
fz install model ./fz-mycode.zip

# Install globally (~/.fz/models/) so every project can use it
fz install model perfectgas --global

# Install an fzd algorithm (into ./.fz/algorithms/ or, with --global, ~/.fz/algorithms/)
fz install algorithm brent
fz install algorithm https://github.com/Funz/fz-PSO

# Remove an installed resource (by name)
fz uninstall model perfectgas
fz uninstall algorithm brent
fz uninstall model perfectgas --global

# See what is installed (models and calculators), optionally validating each
# (fz list does not show algorithms: ls .fz/algorithms, or fz.list_installed_algorithms())
fz list
fz list --check
```

`fz install` requires fz 1.0+.

## Python API

```python
import fz

fz.install_model("perfectgas")                 # → ./.fz/models/
fz.install_model("perfectgas", global_install=True)   # → ~/.fz/models/
fz.install_algorithm("brent")
fz.uninstall_model("perfectgas")
fz.uninstall_algorithm("brent")

fz.list_installed_models()       # dict of installed models
fz.list_installed_algorithms()   # dict of installed algorithms
fz.list_installed_models(global_list=True)   # only ~/.fz/models/
```

`fz.install(...)`, `fz.uninstall(...)` and `fz.list_models(...)` are shorter aliases for the
model functions (`install_model`, `uninstall_model`, `list_installed_models`).
`fz list` (CLI) lists installed models and calculators; there is no `fz list algorithms`
command, use `fz.list_installed_algorithms()`.

## Source resolution

The `source` argument accepts three forms (resolved by `normalize_github_url`):

| Form | Example | Resolves to |
|------|---------|-------------|
| Short name | `perfectgas` | `https://github.com/Funz/fz-perfectgas` (the `fz-` prefix and `Funz` org are assumed) |
| Full GitHub URL | `https://github.com/you/fz-mycode` | that repository's `main` archive |
| Local zip / path | `./fz-mycode.zip` | the local file, unpacked directly |

By convention an installable repository is named `fz-<code>` and ships a `.fz/` directory:

```
fz-mycode/
└── .fz/
    ├── models/MyCode.json          # the model definition (id, varprefix, output parsers)
    ├── calculators/*.json|*.sh     # optional calculator aliases wired to the model
    └── algorithms/*.py|*.R         # for algorithm repositories
```

On install, fz copies every model JSON of the repository (`.fz/models/*.json`; a
repository may ship several related models) into `.fz/models/` (or `~/.fz/models/` with
`--global`) and any accompanying `.fz/` subdirectories (calculators, algorithms, …)
alongside it.

## Install location and discovery

> **Runner paths.** Installed calculator aliases run `bash .fz/calculators/<X>.sh`; such
> `.fz/...` paths are resolved against the `.fz/` directory the alias was loaded from, so a
> `--global` install (in `~/.fz/`) works from any project directory.

- **Project-local** (default): `./.fz/` — visible only inside the current project.
- **Global** (`--global`): `~/.fz/` — visible from every project for the current user.

When the same model, algorithm or calculator exists in both places, the project-level one
(`./.fz/models/`, `./.fz/algorithms/`, ...) wins over the global one, which allows
project-specific customization on top of a personal library of reusable plugins.

Installed models are then referenced by id (`--model MyCode`), and installed calculator
aliases are auto-discovered, so a single-case run needs no `--calculators` argument. See
[Calculators](calculators.md) for calculator aliases and [Model definition](model-definition.md)
for the model JSON structure, and [Core functions](core-functions.md) for `fzl` / `fz list`.

## Using an installed algorithm

Once installed, an algorithm is referenced by name (no path or extension):

```python
results = fz.fzd(
    input_path="input.txt",
    input_variables={"x": "[0;10]", "y": "[-5;5]"},
    model="mymodel",
    output_expression="result",
    algorithm="montecarlo",          # installed plugin name
    calculators=["sh://bash calc.sh"],
    algorithm_options={"batch_sample_size": 20},
)
```

## Creating an algorithm plugin

To share an algorithm as an installable repository:

1. Create a repository named `fz-<algorithm>` (e.g. `fz-montecarlo`).
2. Add the algorithm as `<algorithm>.py` or `<algorithm>.R`, in the repository root or in
   `.fz/algorithms/`. The class interface (`get_initial_design`, `get_next_design`,
   `get_analysis`) is described in [Custom algorithms](custom-algorithms.md); see also
   `examples/algorithms/demo_plugin_system.py` and `examples/algorithm_options_example.md`.
3. Push it to GitHub and share the URL.
4. Install it with `fz install algorithm <name>` or `fz install algorithm <url>`.

Model plugins follow the same `fz-<code>` convention (see "Source resolution" above).
