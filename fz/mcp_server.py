"""
MCP (Model Context Protocol) server exposing fz to AI agents.

Tools: ``fzi``, ``fzc``, ``fzr``, ``fzo``, ``fzl`` (same semantics as the Python API).
Run with ``fz-mcp`` (stdio transport only, see below). Requires the optional ``mcp``
extra: ``pip install 'funz-fz[mcp]'``.

Security posture (trusted by default, restricted mode opt-in):

* File paths are confined to a workspace root (``FZ_MCP_ROOT``, default: the
  current directory).
* The default (trusted) mode gives the agent full API power: templates, formulas,
  output-parsing commands and calculator commands are evaluated/executed without
  isolation - equivalent to giving that agent a shell (see README.md -> "Threat
  Model"). Only use it with trusted agents and inputs.
* With ``FZ_MCP_TRUSTED=0`` (*untrusted* mode), models and calculators must be
  installed aliases (no inline model dict, whose output-parsing commands run in a
  shell; no ``sh://``/``ssh://`` URIs, which run arbitrary commands) - so an agent
  can only run models/calculators a human already installed and vetted. This does
  NOT sandbox formula/template evaluation *inside* fz itself: fz has no such
  isolation mode (deliberately not built - see README.md -> "Threat Model") and
  this restriction does not depend on one.
* Tool annotations (``destructiveHint``/``openWorldHint`` on ``fzc``/``fzr``,
  ``readOnlyHint`` on ``fzi``/``fzo``/``fzl``) tell a well-behaved MCP client what
  each tool can do, but are advisory: **a client that does not honor them can
  still invoke ``fzc``/``fzr`` with attacker-controlled arguments following a
  prompt injection, and in trusted mode that is arbitrary code execution.** The
  annotations reduce accidental damage from a well-behaved client, not from a
  malicious or compromised one.
* Only the ``stdio`` transport is used, and only ``stdio`` is supported without
  an explicit opt-in: set ``FZ_MCP_TRANSPORT`` to ``sse`` or ``streamable-http``
  AND ``FZ_MCP_ALLOW_NETWORK_TRANSPORT=1`` to run a network-facing transport
  (a clear warning is logged when doing so); otherwise the server refuses to
  start rather than silently falling back to stdio.
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from . import core

_NETWORK_TRANSPORTS = ("sse", "streamable-http")


class McpSecurityError(ValueError):
    """Raised when a tool call violates the server's security policy."""


class FzTools:
    """Policy-enforcing wrappers around the fz core functions."""

    def __init__(self, root: Optional[str] = None, trusted: Optional[bool] = None):
        self.root = Path(root or os.environ.get("FZ_MCP_ROOT") or os.getcwd()).resolve()
        self.trusted = (
            os.environ.get("FZ_MCP_TRUSTED", "1").strip().lower() not in ("0", "false", "no", "off")
            if trusted is None else trusted
        )

    # -- policy helpers ---------------------------------------------------
    def _path(self, p: str) -> str:
        path = Path(p)
        path = (path if path.is_absolute() else self.root / path).resolve()
        if path != self.root and self.root not in path.parents:
            raise McpSecurityError(f"Path outside workspace root {self.root}: {p}")
        return str(path)

    def _glob_path(self, p: str) -> str:
        # output paths may contain glob patterns: normalize lexically, then confine
        full = os.path.normpath(os.path.join(str(self.root), p))
        if full != str(self.root) and not full.startswith(str(self.root) + os.sep):
            raise McpSecurityError(f"Path outside workspace root {self.root}: {p}")
        return full

    def _model(self, model: Union[str, Dict]) -> Union[str, Dict]:
        if not self.trusted and not isinstance(model, str):
            raise McpSecurityError("Untrusted mode: model must be an installed alias (string)")
        return model

    def _calculators(self, calculators: Any) -> Any:
        if calculators is None or self.trusted:
            return calculators
        items = calculators if isinstance(calculators, list) else [calculators]
        for c in items:
            if not isinstance(c, str) or "://" in c:
                raise McpSecurityError(
                    "Untrusted mode: calculators must be installed aliases, not URIs or dicts"
                )
        return calculators

    # -- tools ------------------------------------------------------------
    def fzi(self, input_path: str, model: Union[str, Dict]) -> Any:
        """Parse input file(s): variables, formulas, static objects. Read-only."""
        return _jsonable(core.fzi(self._path(input_path), self._model(model)))

    def fzc(self, input_path: str, input_variables: Optional[Dict], model: Union[str, Dict],
            output_dir: str = "output") -> Any:
        """Compile input file(s) with variable values into output_dir.

        Executes the model's templates and formulas as code (see README.md ->
        "Threat Model") and writes files under output_dir.
        """
        core.fzc(self._path(input_path), input_variables, self._model(model),
                 self._path(output_dir))
        return {"output_dir": self._path(output_dir)}

    def fzr(self, input_path: str, input_variables: Optional[Dict], model: Union[str, Dict],
            calculators: Union[str, List[str]], results_dir: str = "results",
            timeout: Optional[int] = None) -> Any:
        """Run a parametric study; returns results as a column dict.

        Executes the model's templates/formulas and the calculator's command as
        code (see README.md -> "Threat Model"), and writes files under results_dir.
        """
        result = core.fzr(self._path(input_path), input_variables, self._model(model),
                          self._path(results_dir), self._calculators(calculators),
                          timeout=timeout)
        return _jsonable(result)

    def fzo(self, output_path: str, model: Union[str, Dict]) -> Any:
        """Parse output file(s) according to the model. Read-only on the filesystem, but
        executes the model's output-parsing commands as code (see README.md -> "Threat Model")."""
        return _jsonable(core.fzo(self._glob_path(output_path), self._model(model)))

    def fzl(self, models: str = "*", calculators: str = "*", check: bool = False) -> Any:
        """List installed models and calculators. Read-only."""
        return _jsonable(core.fzl(models, calculators, check))


def _jsonable(obj: Any) -> Any:
    """Convert DataFrames/numpy values to plain JSON-safe structures."""
    if hasattr(obj, "to_dict") and hasattr(obj, "columns"):
        obj = obj.to_dict(orient="list")
    return json.loads(json.dumps(obj, default=_default))


def _default(o: Any) -> Any:
    if hasattr(o, "tolist"):
        return o.tolist()
    return str(o)


def _tool_annotations():
    """ToolAnnotations for each tool ("mcp.types" is stable across the SDK's major
    versions, unlike the server class - see build_server()). fzd is not exposed
    as an MCP tool (only fzi/fzc/fzr/fzo/fzl are), so it has no annotation here."""
    from mcp.types import ToolAnnotations
    destructive = ToolAnnotations(destructiveHint=True, openWorldHint=True)
    read_only = ToolAnnotations(readOnlyHint=True)
    return {
        "fzi": read_only,
        "fzc": destructive,
        "fzr": destructive,
        "fzo": read_only,
        "fzl": read_only,
    }


def build_server(tools: Optional[FzTools] = None):
    """Create the FastMCP server registering the five fz tools, with hints on
    what each one can do (advisory only - see module docstring)."""
    try:
        try:  # mcp >= 2 renamed FastMCP to MCPServer
            from mcp.server.mcpserver import MCPServer as FastMCP
        except ImportError:
            from mcp.server.fastmcp import FastMCP
    except ImportError as exc:  # pragma: no cover - depends on the optional extra
        raise SystemExit("fz-mcp needs the optional 'mcp' package: pip install 'funz-fz[mcp]'") from exc
    tools = tools or FzTools()
    server = FastMCP("fz")
    annotations = _tool_annotations()
    for name in ("fzi", "fzc", "fzr", "fzo", "fzl"):
        server.tool(name=name, annotations=annotations[name])(getattr(tools, name))
    return server


def _resolve_transport() -> str:
    """stdio unless FZ_MCP_TRANSPORT names a network transport AND
    FZ_MCP_ALLOW_NETWORK_TRANSPORT=1 explicitly opts in (with a warning)."""
    transport = os.environ.get("FZ_MCP_TRANSPORT", "stdio").strip().lower()
    if transport == "stdio" or transport == "":
        return "stdio"
    if transport not in _NETWORK_TRANSPORTS:
        raise SystemExit(
            f"fz-mcp: unknown FZ_MCP_TRANSPORT '{transport}' (expected one of: "
            f"stdio, {', '.join(_NETWORK_TRANSPORTS)})"
        )
    allow = os.environ.get("FZ_MCP_ALLOW_NETWORK_TRANSPORT", "").strip().lower() in ("1", "true", "yes", "on")
    if not allow:
        raise SystemExit(
            f"fz-mcp: refusing to start with network transport '{transport}' - this exposes "
            "fz's tools (in trusted mode, equivalent to shell access - see README.md -> "
            "\"Threat Model\") over the network. Set FZ_MCP_ALLOW_NETWORK_TRANSPORT=1 to "
            "confirm you understand this and want to proceed, ideally combined with "
            "FZ_MCP_TRUSTED=0 and your own network-level authentication."
        )
    print(
        f"fz-mcp: WARNING - starting with network transport '{transport}' "
        f"(FZ_MCP_ALLOW_NETWORK_TRANSPORT=1). See README.md -> \"Threat Model\".",
        file=sys.stderr,
    )
    return transport


def main() -> None:
    transport = _resolve_transport()
    server = build_server()
    server.run(transport=transport)


if __name__ == "__main__":
    main()
