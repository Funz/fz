# MCP server (`fz-mcp`)

**Trusted mode (the default) is equivalent to giving the agent shell access** -
see "Threat Model" above and `doc/mcp-server.md` for the full picture (tool
annotations and their limits, restricted mode, transport).

`fz-mcp` exposes `fzi`, `fzc`, `fzr`, `fzo` and `fzl` as [MCP](https://modelcontextprotocol.io)
tools over `stdio` (the only transport used by default), for any MCP-capable
agent. Install with `pip install 'funz-fz[mcp]'` (Python >= 3.10), then
register it, e.g. for Claude Code: `claude mcp add fz -- fz-mcp`.

Trusted by default (full API power: templates, formulas and models are evaluated without
isolation, so use only with trusted agents and inputs). File paths are always confined
to `FZ_MCP_ROOT` (default: the working directory). Restricted mode is opt-in with
`FZ_MCP_TRUSTED=0`:

- Models and calculators must be installed aliases (no inline model dict, no
  `sh://`/`ssh://` URIs) - the agent can only run models/calculators a human
  already installed and vetted. This restricts what the agent can pass through
  MCP; it does not sandbox formula/template evaluation inside fz itself (fz
  has no such mode, and this restriction does not depend on one).
