"""
Native output extraction for fz models.

This module allows model "output" entries to be evaluated by an extraction
engine other than a shell pipeline, removing (for the ``python://``,
``jq://``, ``yq://`` and ``xpath://`` forms) the dependency on bash and
making output extraction portable across platforms (no bash / FZ_SHELL_PATH
required).

Six forms are supported for the values of ``model["output"]``:

1. Shell command string, implicit default (legacy, unchanged) or explicitly
   marked with the ``bash://`` prefix::

       {"pressure": "grep 'pressure = ' output.txt | awk '{print $3}'"}
       {"pressure": "bash://grep 'pressure = ' output.txt | awk '{print $3}'"}

   Both lines above are equivalent: a plain string with no recognized
   prefix is treated as a shell command for backward compatibility. The
   ``bash://`` prefix lets you say so explicitly, alongside the other
   prefixed forms in the same model. Shell-command outputs require bash
   (and Unix utilities) to be available, including on Windows.

2. Python expression string, marked with the ``python://`` prefix::

       {"pressure": "python://grep(r'pressure = (\\S+)', 'output.txt')"}

   The expression is evaluated with the case output directory as base
   directory. A small set of helper functions is available in the
   expression namespace (see :func:`make_helpers`), plus the ``re``,
   ``json``, ``math``, ``statistics`` modules, ``Path``, and — when
   installed — ``np`` (numpy) and ``pd`` (pandas). No shell is involved.

3. jq expression string, marked with the ``jq://`` prefix, for extracting
   JSON values with the jq command-line tool (https://jqlang.org/)::

       {"energy": "jq://.energy results.json"}

   The part after the prefix is a jq filter followed by the file to read
   (relative to the case output directory), parsed like a shell command
   line (so quoting the filter is optional but allowed). The ``jq``
   executable must be installed and available on ``PATH``; no bash/shell
   is otherwise required.

4. yq expression string, marked with the ``yq://`` prefix, for extracting
   values from YAML (and, since yq auto-detects by extension, JSON, XML or
   TOML) with the mikefarah/yq command-line tool
   (https://github.com/mikefarah/yq)::

       {"version": "yq://.metadata.version config.yaml"}

   Same syntax as ``jq://`` (filter then file, shell-style parsed). The
   ``yq`` executable must be installed and available on ``PATH``; no
   bash/shell is otherwise required. Note: this refers to the Go-based
   mikefarah/yq (the ``jq``-like YAML processor); the unrelated
   Python-based kislyuk/yq package uses different flags and is not what
   this prefix targets.

5. XPath expression string, marked with the ``xpath://`` prefix, for
   extracting values from XML files with ``xmllint --xpath``
   (part of libxml2, https://gitlab.gnome.org/GNOME/libxml2)::

       {"pressure": "xpath://'//result/pressure/text()' output.xml"}

   Same syntax as ``jq://`` (expression then file, shell-style parsed).
   The ``xmllint`` executable must be installed and available on ``PATH``;
   no bash/shell is otherwise required. The result is the raw text matched
   by the XPath expression, cast to int/float when possible (like
   :func:`grep`'s default casting).

6. Python callable (Python API only). The callable receives the case output
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
import shlex as _shlex
import shutil as _shutil
import statistics as _statistics
import subprocess as _subprocess
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Union

from .logging import log_debug

#: Prefix marking a model output entry as a native Python expression
PYTHON_OUTPUT_PREFIX = "python://"

#: Prefix marking a model output entry as a jq filter (requires the ``jq``
#: executable to be installed on the system)
JQ_OUTPUT_PREFIX = "jq://"

#: Prefix marking a model output entry as a yq filter (requires the
#: mikefarah/yq executable to be installed on the system)
YQ_OUTPUT_PREFIX = "yq://"

#: Prefix marking a model output entry as an XPath expression (requires the
#: ``xmllint`` executable, from libxml2, to be installed on the system)
XPATH_OUTPUT_PREFIX = "xpath://"

#: Prefix explicitly marking a model output entry as a shell command. This
#: is the implicit default for any output string without a recognized
#: prefix, kept for backward compatibility; ``bash://`` lets you say so
#: explicitly when mixing output kinds in the same model.
BASH_OUTPUT_PREFIX = "bash://"


def is_python_expression(spec: Any) -> bool:
    """Return True if an output spec string is a ``python://`` expression."""
    return isinstance(spec, str) and spec.lstrip().lower().startswith(
        PYTHON_OUTPUT_PREFIX
    )


def strip_python_prefix(spec: str) -> str:
    """Remove the ``python://`` prefix from an output spec string."""
    return spec.lstrip()[len(PYTHON_OUTPUT_PREFIX):].strip()


def is_jq_expression(spec: Any) -> bool:
    """Return True if an output spec string is a ``jq://`` filter."""
    return isinstance(spec, str) and spec.lstrip().lower().startswith(
        JQ_OUTPUT_PREFIX
    )


def strip_jq_prefix(spec: str) -> str:
    """Remove the ``jq://`` prefix from an output spec string."""
    return spec.lstrip()[len(JQ_OUTPUT_PREFIX):].strip()


def is_yq_expression(spec: Any) -> bool:
    """Return True if an output spec string is a ``yq://`` filter."""
    return isinstance(spec, str) and spec.lstrip().lower().startswith(
        YQ_OUTPUT_PREFIX
    )


def strip_yq_prefix(spec: str) -> str:
    """Remove the ``yq://`` prefix from an output spec string."""
    return spec.lstrip()[len(YQ_OUTPUT_PREFIX):].strip()


def is_xpath_expression(spec: Any) -> bool:
    """Return True if an output spec string is an ``xpath://`` expression."""
    return isinstance(spec, str) and spec.lstrip().lower().startswith(
        XPATH_OUTPUT_PREFIX
    )


def strip_xpath_prefix(spec: str) -> str:
    """Remove the ``xpath://`` prefix from an output spec string."""
    return spec.lstrip()[len(XPATH_OUTPUT_PREFIX):].strip()


def is_bash_expression(spec: Any) -> bool:
    """
    Return True if an output spec string is a shell command: either
    explicitly marked with ``bash://``, or a plain string with no
    recognized prefix (the implicit legacy default).
    """
    if not isinstance(spec, str):
        return False
    if (
        is_python_expression(spec)
        or is_jq_expression(spec)
        or is_yq_expression(spec)
        or is_xpath_expression(spec)
    ):
        return False
    return True


def strip_bash_prefix(spec: str) -> str:
    """Remove an explicit ``bash://`` prefix, if present, from a spec string."""
    stripped = spec.lstrip()
    if stripped.lower().startswith(BASH_OUTPUT_PREFIX):
        return stripped[len(BASH_OUTPUT_PREFIX):].strip()
    return spec


def _cast_numeric(value: str) -> Any:
    """Cast a string to int/float when possible, otherwise return it as-is."""
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value


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
            return _cast_numeric(value) if cast else value

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


def evaluate_jq_output(
    spec: str,
    output_dir: Union[str, Path],
) -> Any:
    """
    Evaluate a ``jq://`` output spec for one case output directory using the
    system ``jq`` executable.

    Args:
        spec: A ``jq://``-prefixed spec string, or a bare ``"<filter> <file>"``
            string (prefix already stripped). The filter and file are parsed
            shell-style (``shlex``), so quoting the filter is optional but
            allowed, e.g. ``"jq://.energy results.json"`` or
            ``"jq://'.a.b[0]' results.json"``. The file is resolved relative
            to the case output directory.
        output_dir: The case output directory.

    Returns:
        The JSON value produced by ``jq``, decoded to native Python types
        (str/int/float/bool/None/list/dict) via ``json.loads`` of jq's
        (non-raw) output.

    Raises:
        RuntimeError: If the ``jq`` executable is not found on PATH.
        ValueError: If the spec does not include both a filter and a file.
        subprocess.CalledProcessError: If ``jq`` exits with a non-zero
            status (e.g. invalid filter or malformed JSON input).
    """
    if _shutil.which("jq") is None:
        raise RuntimeError(
            "The 'jq://' output prefix requires the 'jq' executable to be "
            "installed and available on PATH. See https://jqlang.org/download/ "
            "for installation instructions."
        )

    out_dir = Path(output_dir)
    expr = strip_jq_prefix(spec) if is_jq_expression(spec) else spec
    tokens = _shlex.split(expr)
    if len(tokens) < 2:
        raise ValueError(
            "Invalid 'jq://' output spec: expected a filter followed by a "
            f"file, got {spec!r}"
        )
    jq_filter, file_arg = tokens[0], tokens[-1]
    file_path = Path(file_arg)
    if not file_path.is_absolute():
        file_path = out_dir / file_path

    log_debug(f"Evaluating jq output filter: {jq_filter} on {file_path}")
    result = _subprocess.run(
        ["jq", jq_filter, str(file_path)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise _subprocess.CalledProcessError(
            result.returncode, ["jq", jq_filter, str(file_path)],
            output=result.stdout, stderr=result.stderr,
        )

    return _json.loads(result.stdout.strip())


def evaluate_yq_output(
    spec: str,
    output_dir: Union[str, Path],
) -> Any:
    """
    Evaluate a ``yq://`` output spec for one case output directory using the
    system ``yq`` executable (mikefarah/yq — a jq-like processor for YAML,
    and, via extension auto-detection, JSON/XML/TOML too).

    Args:
        spec: A ``yq://``-prefixed spec string, or a bare ``"<filter> <file>"``
            string (prefix already stripped). Same shell-style parsing as
            :func:`evaluate_jq_output`, e.g. ``"yq://.metadata.version
            config.yaml"``. The file is resolved relative to the case
            output directory.
        output_dir: The case output directory.

    Returns:
        The value produced by ``yq`` (invoked with ``-o=json`` for a
        consistent, unambiguous result), decoded to native Python types via
        ``json.loads``.

    Raises:
        RuntimeError: If the ``yq`` executable is not found on PATH.
        ValueError: If the spec does not include both a filter and a file.
        subprocess.CalledProcessError: If ``yq`` exits with a non-zero
            status (e.g. invalid filter or malformed input).
    """
    if _shutil.which("yq") is None:
        raise RuntimeError(
            "The 'yq://' output prefix requires the 'yq' executable "
            "(mikefarah/yq) to be installed and available on PATH. See "
            "https://github.com/mikefarah/yq#install for installation "
            "instructions."
        )

    out_dir = Path(output_dir)
    expr = strip_yq_prefix(spec) if is_yq_expression(spec) else spec
    tokens = _shlex.split(expr)
    if len(tokens) < 2:
        raise ValueError(
            "Invalid 'yq://' output spec: expected a filter followed by a "
            f"file, got {spec!r}"
        )
    yq_filter, file_arg = tokens[0], tokens[-1]
    file_path = Path(file_arg)
    if not file_path.is_absolute():
        file_path = out_dir / file_path

    log_debug(f"Evaluating yq output filter: {yq_filter} on {file_path}")
    cmd = ["yq", "-o=json", yq_filter, str(file_path)]
    result = _subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise _subprocess.CalledProcessError(
            result.returncode, cmd, output=result.stdout, stderr=result.stderr,
        )

    return _json.loads(result.stdout.strip())


def evaluate_xpath_output(
    spec: str,
    output_dir: Union[str, Path],
) -> Any:
    """
    Evaluate an ``xpath://`` output spec for one case output directory using
    the system ``xmllint`` executable (``xmllint --xpath``, part of
    libxml2).

    Args:
        spec: An ``xpath://``-prefixed spec string, or a bare
            ``"<expression> <file>"`` string (prefix already stripped).
            Same shell-style parsing as :func:`evaluate_jq_output`, e.g.
            ``"xpath://'//result/pressure/text()' output.xml"``. The file
            is resolved relative to the case output directory.
        output_dir: The case output directory.

    Returns:
        The raw text matched by the XPath expression, cast to int/float
        when possible (same casting as :func:`grep`'s default), otherwise
        returned as a string. If the expression selects a node-set with
        more than one node (a vector output — e.g. ``//result/value/text()``
        matching several ``<value>`` elements), a list of per-node values
        (each cast individually) is returned instead of a single
        concatenated string.

    Raises:
        RuntimeError: If the ``xmllint`` executable is not found on PATH.
        ValueError: If the spec does not include both an expression and a
            file.
        subprocess.CalledProcessError: If ``xmllint`` exits with a
            non-zero status (e.g. invalid expression, no match, or
            malformed XML).
    """
    if _shutil.which("xmllint") is None:
        raise RuntimeError(
            "The 'xpath://' output prefix requires the 'xmllint' "
            "executable (libxml2) to be installed and available on PATH."
        )

    out_dir = Path(output_dir)
    expr = strip_xpath_prefix(spec) if is_xpath_expression(spec) else spec
    tokens = _shlex.split(expr)
    if len(tokens) < 2:
        raise ValueError(
            "Invalid 'xpath://' output spec: expected an XPath expression "
            f"followed by a file, got {spec!r}"
        )
    xpath_expr, file_arg = tokens[0], tokens[-1]
    file_path = Path(file_arg)
    if not file_path.is_absolute():
        file_path = out_dir / file_path

    def _run_xpath(one_expr: str) -> _subprocess.CompletedProcess:
        cmd = ["xmllint", "--xpath", one_expr, str(file_path)]
        return _subprocess.run(cmd, capture_output=True, text=True)

    # First, find out whether the expression selects a node-set, and if so
    # how many nodes it matches. xmllint concatenates the serialized text
    # of every matched node with no separator we can rely on, so a naive
    # single call cannot distinguish "one node" from "several nodes whose
    # text happens to contain no digits/whitespace" reliably. Wrapping the
    # expression in count(...) tells us unambiguously: it succeeds (with an
    # integer result) only when the expression evaluates to a node-set,
    # and fails with "Invalid type" when it already returns a scalar
    # (string/number/boolean, e.g. from count()/sum()/string() themselves).
    log_debug(f"Evaluating xpath output expression: {xpath_expr} on {file_path}")
    count_result = _run_xpath(f"count({xpath_expr})")
    node_count: Optional[int] = None
    if count_result.returncode == 0:
        try:
            node_count = int(count_result.stdout.strip())
        except ValueError:
            node_count = None

    if node_count is not None and node_count > 1:
        # Vector output: fetch and cast each matched node individually so
        # embedded whitespace/newlines in node text can never corrupt the
        # split, unlike naively splitting the concatenated output.
        values = []
        for i in range(1, node_count + 1):
            indexed_result = _run_xpath(f"({xpath_expr})[{i}]")
            if indexed_result.returncode != 0:
                cmd = ["xmllint", "--xpath", f"({xpath_expr})[{i}]", str(file_path)]
                raise _subprocess.CalledProcessError(
                    indexed_result.returncode, cmd,
                    output=indexed_result.stdout, stderr=indexed_result.stderr,
                )
            values.append(_cast_numeric(indexed_result.stdout.strip()))
        return values

    # Scalar path (0 or 1 matched node, or an expression that already
    # evaluates to a scalar) — unchanged, backward-compatible behavior.
    result = _run_xpath(xpath_expr)
    if result.returncode != 0:
        cmd = ["xmllint", "--xpath", xpath_expr, str(file_path)]
        raise _subprocess.CalledProcessError(
            result.returncode, cmd, output=result.stdout, stderr=result.stderr,
        )

    return _cast_numeric(result.stdout.strip())
