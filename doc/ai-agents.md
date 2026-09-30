# Using fz with AI Coding Agents

An [Agent Skill](https://agentskills.io) is bundled in [`skills/fz/`](../skills/fz/) to teach
AI coding agents (Claude Code, and other agents supporting the skills format) the fz
workflow: parameterizing input files, defining models, choosing calculators, and running
parametric studies.

**Easiest (Claude Code plugin)** — install straight from Claude Code, no shell needed:

```
/plugin marketplace add Funz/fz
/plugin install fz@funz
```

The skill then loads automatically in every project, and updates with the marketplace.
The plugin also adds four slash commands — `/fz:wrap`, `/fz:run`, `/fz:design`,
`/fz:install` — that pre-frame the corresponding workflow.

**Manual install** — copy (or symlink) the skill into your project or user skills
directory:

```bash
# Project-level (recommended): available to anyone working in the project
mkdir -p .claude/skills
cp -r /path/to/fz/skills/fz .claude/skills/

# Or user-level: available in all your projects
mkdir -p ~/.claude/skills
cp -r /path/to/fz/skills/fz ~/.claude/skills/
```

Then just ask the agent things like *"wrap my simulation code with fz and run a parameter
study over mesh_size and timestep"* — the skill is loaded automatically when relevant.

The skill contains:

- **skills/fz/SKILL.md** - Step-by-step workflow for wrapping a simulation code
- **skills/fz/reference.md** - Condensed API/CLI reference, JSON schemas, environment variables
- **skills/fz/algorithm-wrapper.md** - Interface for writing custom fzd algorithms

See **[skills/howto.md](../skills/howto.md)** for a complete walkthrough with example prompts
(parametric studies, SSH execution, cache reuse, optimization, headless usage).
