# MCP server

**Giving an agent access to `fz-mcp` in its default (trusted) mode is
equivalent to giving that agent shell access**: templates, formulas,
output-parsing commands and calculator commands all run as code, with your
user's privileges (see `README.md` → "Threat Model"). Only register it for
agents and inputs you trust.

`fz-mcp` exposes `fzi`, `fzc`, `fzr`, `fzo` and `fzl` as [MCP](https://modelcontextprotocol.io)
tools over `stdio` (the only transport used, see "Transport" below), for any
MCP-capable agent. Install with `pip install 'funz-fz[mcp]'` (Python >= 3.10),
then register it, e.g. for Claude Code: `claude mcp add fz -- fz-mcp`.

## Tool annotations

Each tool is registered with [MCP tool annotations](https://modelcontextprotocol.io)
describing what it can do: `fzc` and `fzr` (which write files and run a
calculator command) get `destructiveHint: true` and `openWorldHint: true`;
`fzi`, `fzo` and `fzl` (which only read/parse) get `readOnlyHint: true`.

These annotations are **advisory**: they help a well-behaved MCP client warn a
person or ask for confirmation before a destructive call, but a client that
does not honor them can still call `fzc`/`fzr` with attacker-controlled
arguments following a prompt injection - and in trusted mode, that is
arbitrary code execution. The annotations reduce accidental damage from a
well-behaved client; they are not a security boundary against a malicious or
compromised one.

## Trusted vs. restricted mode

Trusted by default (full API power: templates, formulas and models are
evaluated without isolation). File paths are always confined to
`FZ_MCP_ROOT` (default: the working directory). Restricted mode is opt-in
with `FZ_MCP_TRUSTED=0`:

- Models and calculators must be installed aliases (no inline model dict, no
  `sh://`/`ssh://` URIs) - so the agent can only run models/calculators a
  human already installed and vetted ahead of time.
- This restricts what the *agent* can pass to fz through MCP; it does not
  sandbox formula/template evaluation *inside* fz itself. fz has no such
  isolation mode and this restriction does not depend on one - see
  `README.md` → "Threat Model" for why (isolation was considered and
  deliberately not built; it would break real, existing usage of input
  templates and output parsers).

## Transport

Only the `stdio` transport is used by default, and it's the only one that
starts without an explicit opt-in. A network-facing transport (`sse` or
`streamable-http`) requires setting **both** `FZ_MCP_TRANSPORT` to that value
**and** `FZ_MCP_ALLOW_NETWORK_TRANSPORT=1`; a warning is logged when doing so.
Without that opt-in, requesting a network transport refuses to start rather
than silently falling back to `stdio`. Combine a network transport with
`FZ_MCP_TRUSTED=0` and your own network-level authentication - `fz-mcp` does
not authenticate clients itself.
