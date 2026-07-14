"""
Native Python output extraction for fz models.

This module allows model "output" entries to be evaluated as Python
expressions (or callables) instead of shell command pipelines, removing the
dependency on external tools like grep/awk/sed and making output extraction
fully portable across platforms (no bash / FZ_SHELL_PATH required).

Three forms are supported for the values of ``model["output"]``:

1. Shell command string (legacy, unchanged)::

       {"pressure": "grep 'pressure = ' output.txt | awk '{print $3}'"}

2. Python expression string, marked with the ``python:`` prefix::

       {"pressure": "python: grep(r'pressure = (\\S+)', 'output.txt')"}

   The expression is evaluated with the case output directory as base
   directory. A small set of helper functions is available in the
   expression namespace (see :func:`make_helpers`), plus the ``re``,
   ``json``, ``math``, ``statistics`` modules, ``Path``, and — when
   installed — ``np`` (numpy) and ``pd`` (pandas).

3. Python callable (Python API only). The callable receives the case output
   directory as a ``pathlib.Path`` and returns the parsed value::

       {"pressure": lambda d: float((d / "pressure.txt").read_text())}

Security note: Python expressions are evaluated with ``eval`` in a dedicated
namespace. This is the same trust model as the legacy shell commands, which
are executed verbatim in a shell: the model definition is trusted content
authored by the user. Do not evaluate model files from untrusted sources.
"""

import json as _json
import math as _math
import re as _re
import statistics as _statistics
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Union

from .logging import log_debug

#: Prefix marking a model output entry as a native Python expression
PYTHON_OUTPUT_PREFIX = "python:"


def is_python_expression(spec: Any) -> bool:
    """Return True if an output spec string is a Python expression."""
    return isinstance(spec, str) and spec.lstrip().lower().startswith(
        PYTHON_OUTPUT_PREFIX
    )


def strip_python_prefix(spec: str) -> str:
    """Remove the ``python:`` prefix from an output spec string."""
    return spec.lstrip()[len(PYTHON_OUTPUT_PREFIX):].strip()


def make_helpers(base_dir: Union[str, Path]) -> Dict[str, Any]:
    """
    Build the helper namespace available to Python output expressions.

    All path arguments accepted by the helpers are resolved relative to
    ``base_dir`` (the case output directory), so expressions behave like the
    legacy shell commands which run with cwd set to that directory.

    Helpers:
        read(path)                  -> file content as str
        lines(path)                 -> list of lines (no trailing newlines)
        line(path, n)               -> n-th line (0-based; negative from end)
        grep(pattern, path, ...)    -> regex extraction (see docstring)
        json_file(path)             -> parsed JSON content
        csv_file(path, column=None) -> pandas DataFrame, or column as list
    """
    base = Path(base_dir)

    def _resolve(path: Union[str, Path]) -> Path:
        p = Path(path)
        return p if p.is_absolute() else (base / p)

    def read(path: Union[str, Path]) -> str:
        """Return the full content of a file as a string."""
        return _resolve(path).read_text()

    def lines(path: Union[str, Path]) -> list:
        """Return the list of lines of a file (without line endings)."""
        return read(path).splitlines()

    def line(path: Union[str, Path], n: int) -> str:
        """Return the n-th line of a file (0-based, negative from end)."""
        return lines(path)[n]

    def grep(
        pattern: str,
        path: Union[str, Path],
        group: Optional[int] = None,
        all: bool = False,
        cast: bool = True,
    ) -> Any:
        """
        Extract values from a file with a regular expression.

        Args:
            pattern: Regular expression. If it contains capture groups, the
                first group is returned by default; otherwise the whole match.
            path: File to search, relative to the case output directory.
            group: Explicit group index to return (overrides the default).
            all: If True, return the list of all matches; otherwise the first.
            cast: If True (default), cast numeric-looking results to
                int/float.

        Returns:
            The matched value (or list of values with ``all=True``), or None
            if no match is found.
        """
        regex = _re.compile(pattern, _re.MULTILINE)
        content = read(path)

        if group is None:
            group = 1 if regex.groups >= 1 else 0

        def _cast(value: str) -> Any:
            if not cast:
                return value
            try:
                return int(value)
            except ValueError:
                pass
            try:
                return float(value)
            except ValueError:
                return value

        if all:
            return [_cast(m.group(group)) for m in regex.finditer(content)]
        match = regex.search(content)
        return _cast(match.group(group)) if match else None

    def json_file(path: Union[str, Path]) -> Any:
        """Parse a JSON file and return its content."""
        return _json.loads(read(path))

    def csv_file(path: Union[str, Path], column: Optional[str] = None) -> Any:
        """
        Load a CSV file with pandas.

        Returns the DataFrame, or the given column as a plain list when
        ``column`` is provided.
        """
        import pandas as pd  # fz already depends on pandas

        df = pd.read_csv(_resolve(path))
        if column is not None:
            return df[column].tolist()
        return df

    def hdf5_file(path: Union[str, Path], dataset: Optional[str] = None) -> Any:
        """
        Read a dataset from an HDF5 file (requires the optional ``h5py``
        dependency: ``pip install h5py``).

        Args:
            path: HDF5 file, relative to the case output directory.
            dataset: Dataset name or path within the file (e.g.
                ``"results/temperature"``). When omitted, returns the list of
                top-level keys, which is convenient for exploration.

        Returns:
            The dataset content converted to native Python types (scalars,
            lists, str) for clean DataFrame/JSON round-trips, or the list of
            top-level keys when ``dataset`` is None.
        """
        try:
            import h5py
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "The hdf5_file() output helper requires the optional 'h5py' "
                "package: pip install h5py"
            ) from exc

        with h5py.File(_resolve(path), "r") as f:
            if dataset is None:
                return list(f.keys())
            data = f[dataset][()]

        # Convert to native Python types
        import numpy as np

        if isinstance(data, np.ndarray):
            data = data.tolist()
        elif isinstance(data, np.generic):
            data = data.item()
        if isinstance(data, bytes):
            data = data.decode()
        elif isinstance(data, list):
            data = [d.decode() if isinstance(d, bytes) else d for d in data]
        return data

    helpers: Dict[str, Any] = {
        # helper functions
        "read": read,
        "lines": lines,
        "line": line,
        "grep": grep,
        "json_file": json_file,
        "csv_file": csv_file,
        "hdf5_file": hdf5_file,
        # convenient modules / names
        "re": _re,
        "json": _json,
        "math": _math,
        "statistics": _statistics,
        "Path": Path,
        "base_dir": base,
    }

    # Optional scientific stack (numpy ships with pandas, but stay defensive)
    try:
        import numpy as np

        helpers["np"] = np
    except ImportError:  # pragma: no cover
        pass
    try:
        import pandas as pd

        helpers["pd"] = pd
    except ImportError:  # pragma: no cover
        pass

    return helpers


def evaluate_python_output(
    spec: Union[str, Callable[[Path], Any]],
    output_dir: Union[str, Path],
) -> Any:
    """
    Evaluate a native Python output spec for one case output directory.

    Args:
        spec: Either a ``python:``-prefixed expression string, a bare
            expression string (prefix already stripped), or a callable taking
            the output directory Path.
        output_dir: The case output directory.

    Returns:
        The extracted value (any Python type; numpy scalars are converted to
        native Python types for clean DataFrame/JSON round-trips).

    Raises:
        Exception: Propagates any error raised by the expression/callable;
            the caller is responsible for error reporting (consistent with
            legacy shell command handling in fzo).
    """
    out_dir = Path(output_dir)

    if callable(spec):
        value = spec(out_dir)
    else:
        expr = strip_python_prefix(spec) if is_python_expression(spec) else spec
        namespace = make_helpers(out_dir)
        log_debug(f"Evaluating python output expression: {expr}")
        value = eval(expr, {"__builtins__": __builtins__}, namespace)

    # Normalize numpy scalar types to native Python for consistency
    try:
        import numpy as np

        if isinstance(value, np.generic):
            value = value.item()
    except ImportError:  # pragma: no cover
        pass

    return value
