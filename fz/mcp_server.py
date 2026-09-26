"""
MCP (Model Context Protocol) server exposing fz to AI agents.

Tools: ``fzi``, ``fzc``, ``fzr``, ``fzo``, ``fzl`` (same semantics as the Python API).
Run with ``fz-mcp`` (stdio transport). Requires the optional ``mcp`` extra:
``pip install 'funz-fz[mcp]'``.

Security posture (trusted by default, restricted mode opt-in and fail closed):

* File paths are confined to a workspace root (``FZ_MCP_ROOT``, default: the
  current directory).
* With ``FZ_MCP_TRUSTED=0`` (*untrusted* mode), models must be installed aliases (no inline
  model dict, whose output commands run in a shell) and calculators must be
  installed aliases (no ``sh://``/``ssh://`` URIs, which run arbitrary commands),
  and fz is called with ``trusted=False`` so formulas are not ``eval``-ed.
  If the installed fz has no ``trusted`` parameter yet, untrusted mode cannot be
  enforced and the server refuses to start.
* The default (trusted) mode gives the agent full API power: templates, formulas
  and models are evaluated/executed without isolation. Only use it with trusted
  agents and inputs.
"""

import inspect
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from . import core


class McpSecurityError(ValueError):
    """Raised when a tool call violates the server's security policy."""


def _core_supports_trusted() -> bool:
    return "trusted" in inspect.signature(core.fzr).parameters


class FzTools:
    """Policy-enforcing wrappers around the fz core functions."""

    def __init__(self, root: Optional[str] = None, trusted: Optional[bool] = None):
        self.root = Path(root or os.environ.get("FZ_MCP_ROOT") or os.getcwd()).resolve()
        self.trusted = (
            os.environ.get("FZ_MCP_TRUSTED", "1").strip().lower() not in ("0", "false", "no", "off")
            if trusted is None else trusted
        )
        if not self.trusted and not _core_supports_trusted():
            raise McpSecurityError(
                "Untrusted mode requires an fz core with a 'trusted' parameter, which "
                "this fz version lacks. Upgrade fz, or drop FZ_MCP_TRUSTED=0 to accept "
                "that templates and formulas are evaluated without isolation."
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

    def _kw(self) -> Dict[str, Any]:
        return {} if self.trusted else {"trusted": False}

    # -- tools ------------------------------------------------------------
    def fzi(self, input_path: str, model: Union[str, Dict]) -> Any:
        """Parse input file(s): variables, formulas, static objects."""
        return _jsonable(core.fzi(self._path(input_path), self._model(model)))

    def fzc(self, input_path: str, input_variables: Optional[Dict], model: Union[str, Dict],
            output_dir: str = "output") -> Any:
        """Compile input file(s) with variable values into output_dir."""
        core.fzc(self._path(input_path), input_variables, self._model(model),
                 self._path(output_dir), **self._kw())
        return {"output_dir": self._path(output_dir)}

    def fzr(self, input_path: str, input_variables: Optional[Dict], model: Union[str, Dict],
            calculators: Union[str, List[str]], results_dir: str = "results",
            timeout: Optional[int] = None) -> Any:
        """Run a parametric study; returns results as a column dict."""
        result = core.fzr(self._path(input_path), input_variables, self._model(model),
                          self._path(results_dir), self._calculators(calculators),
                          timeout=timeout, **self._kw())
        return _jsonable(result)

    def fzo(self, output_path: str, model: Union[str, Dict]) -> Any:
        """Parse output file(s) according to the model."""
        return _jsonable(core.fzo(self._glob_path(output_path), self._model(model)))

    def fzl(self, models: str = "*", calculators: str = "*", check: bool = False) -> Any:
        """List installed models and calculators."""
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


def build_server(tools: Optional[FzTools] = None):
    """Create the FastMCP server registering the five fz tools."""
    try:
        try:  # mcp >= 2 renamed FastMCP to MCPServer
            from mcp.server.mcpserver import MCPServer as FastMCP
        except ImportError:
            from mcp.server.fastmcp import FastMCP
    except ImportError as exc:  # pragma: no cover - depends on the optional extra
        raise SystemExit("fz-mcp needs the optional 'mcp' package: pip install 'funz-fz[mcp]'") from exc
    tools = tools or FzTools()
    server = FastMCP("fz")
    for name in ("fzi", "fzc", "fzr", "fzo", "fzl"):
        server.tool(name=name)(getattr(tools, name))
    return server


def main() -> None:
    try:
        server = build_server()
    except McpSecurityError as exc:
        raise SystemExit(f"fz-mcp: {exc}")
    server.run()


if __name__ == "__main__":
    main()
