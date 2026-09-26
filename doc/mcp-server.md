# MCP server

`fz-mcp` exposes `fzi`, `fzc`, `fzr`, `fzo` and `fzl` as [MCP](https://modelcontextprotocol.io)
tools over stdio, for any MCP-capable agent. Install with `pip install 'funz-fz[mcp]'`
(Python >= 3.10), then register it, e.g. for Claude Code:
`claude mcp add fz -- fz-mcp`.

Safe by default:

- File paths are confined to `FZ_MCP_ROOT` (default: the working directory).
- Default *untrusted* mode: models and calculators must be installed aliases (no inline
  model dict, no `sh://`/`ssh://` URIs), and fz is called with `trusted=False`. If the
  installed fz core has no `trusted` parameter yet, the server refuses to start.
- `FZ_MCP_TRUSTED=1` lifts these restrictions (full API power; templates and formulas are
  evaluated without isolation). Use only with trusted agents and inputs.

