# MCP server

`fz-mcp` exposes `fzi`, `fzc`, `fzr`, `fzo` and `fzl` as [MCP](https://modelcontextprotocol.io)
tools over stdio, for any MCP-capable agent. Install with `pip install 'funz-fz[mcp]'`
(Python >= 3.10), then register it, e.g. for Claude Code:
`claude mcp add fz -- fz-mcp`.

Trusted by default (full API power: templates, formulas and models are evaluated without
isolation, so use only with trusted agents and inputs). File paths are always confined
to `FZ_MCP_ROOT` (default: the working directory). Restricted mode is opt-in with
`FZ_MCP_TRUSTED=0`:

- Models and calculators must be installed aliases (no inline model dict, no
  `sh://`/`ssh://` URIs), and fz is called with `trusted=False`. If the installed fz core
  has no `trusted` parameter yet, the server refuses to start in this mode.
