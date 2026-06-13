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
fz install algorithm https://github.com/Funz/fz-montecarlo

# Remove an installed resource (by name)
fz uninstall model perfectgas
fz uninstall algorithm brent
fz uninstall model perfectgas --global

# See what is installed (models and calculators), optionally validating each
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
```

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

On install, fz copies the model JSON into `.fz/models/` (or `~/.fz/models/` with
`--global`) and any accompanying `.fz/` subdirectories (calculators, algorithms, …)
alongside it.

## Install location and discovery

- **Project-local** (default): `./.fz/` — visible only inside the current project.
- **Global** (`--global`): `~/.fz/` — visible from every project for the current user.

Installed models are then referenced by id (`--model MyCode`), and installed calculator
aliases are auto-discovered, so a single-case run needs no `--calculators` argument. See
[Calculators](calculators.md) for calculator aliases and [Model definition](model-definition.md)
for the model JSON structure, and [Core functions](core-functions.md) for `fzl` / `fz list`.
