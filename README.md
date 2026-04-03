<div align="center">

# Personal Agent Toolkit

**A local-first Python toolkit for building and running personal coding agents**

![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Tests](https://img.shields.io/badge/tests-passing-brightgreen)
![Scope](https://img.shields.io/badge/scope-local--first-orange)
![Status](https://img.shields.io/badge/status-public--ready-success)

**Claude-native + OpenAI-compatible + plugins + workflows + planning + memory**

</div>

---

## Why this project exists

Most agent frameworks are either:

- too heavyweight for personal workflows
- too coupled to one model provider
- too hard to customize locally
- too opaque when you want to inspect what the agent is doing

**Personal Agent Toolkit** exists to give you a simpler path:

- a **local-first** runtime
- a **Python-native** codebase
- support for **Claude** and **OpenAI-compatible models**
- built-in **plugins**, **skills**, **memory**, **planning**, and **subagents**
- an architecture you can actually read, fork, and extend

If you want a repo that is useful for **personal use**, **research**, or **open-source collaboration**, this is the goal.

---

## Why it matters

### 1. Local-first by default

Your workflows, notes, plans, skills, and plugins live in the repo and on your machine first.

That makes the toolkit easier to:

- understand
- debug
- customize
- trust for day-to-day use

### 2. Works with Claude and other LLMs

You can run:

- native Anthropic / Claude
- OpenAI-compatible backends
- local model gateways

That means you are not locked into one vendor or one serving stack.

### 3. Built for extension

The project includes:

- plugin manifests
- workflow execution
- skill prompts
- MCP-style local resource registry
- planning and memory

So you can evolve it into your own personal agent environment instead of treating it like a black box.

### 4. Open-source friendly

The repository includes:

- MIT license
- contributing guide
- code of conduct
- security policy
- CI
- issue and PR templates

So it is ready for public iteration, collaboration, and research use.

---

## Quickstart

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .
python -m personal_agent_toolkit --prompt "/help"
```

Interactive mode:

```bash
python -m personal_agent_toolkit
```

---

## Demo

### Demo 1 — startup and command flow

> Replace this with a GIF or screenshot:
>
> `docs/demo-startup.gif`

Suggested capture:

- start the CLI
- run `/agents`
- switch with `/agent coder`
- set a plan with `/plan-set`

---

### Demo 2 — workflow + memory

> Replace this with a GIF or screenshot:
>
> `docs/demo-workflow-memory.gif`

Suggested capture:

- run `/workflow capture-note release-checklist`
- run `/memory`
- run `/memory-search release`

---

### Demo 3 — file automation

> Replace this with a GIF or screenshot:
>
> `docs/demo-editing.gif`

Suggested capture:

- `/grep TODO .`
- `/patch-preview ...`
- `/replace-block ...`
- `/diff ...`

---

## Core capabilities

- local CLI/REPL agent runtime
- native Anthropic / Claude support
- OpenAI-compatible provider support
- file operations, shell execution, grep, glob, diff, patch previews
- persistent notes and planning
- markdown-based skills
- lightweight plugins and workflows
- local MCP-style resource registry
- delegate / spawn / wait subagent flows

---

## Model and provider configuration

The runtime currently supports:

- `echo` for smoke testing
- `anthropic` / `claude` for native Claude access
- `openai` / `openai-compatible` for OpenAI-style endpoints

### Environment variables

```bash
PERSONAL_AGENT_TOOLKIT_PROVIDER
PERSONAL_AGENT_TOOLKIT_BASE_URL
PERSONAL_AGENT_TOOLKIT_API_KEY
PERSONAL_AGENT_TOOLKIT_MODEL
PERSONAL_AGENT_TOOLKIT_TIMEOUT
PERSONAL_AGENT_TOOLKIT_DEBUG
PERSONAL_AGENT_TOOLKIT_ANTHROPIC_VERSION
PERSONAL_AGENT_TOOLKIT_MAX_TOKENS
```

### Native Claude example

```powershell
$env:PERSONAL_AGENT_TOOLKIT_PROVIDER="anthropic"
$env:PERSONAL_AGENT_TOOLKIT_API_KEY="your-anthropic-api-key"
$env:PERSONAL_AGENT_TOOLKIT_MODEL="claude-sonnet-4-5"
python -m personal_agent_toolkit
```

### OpenAI-compatible example

```powershell
$env:PERSONAL_AGENT_TOOLKIT_PROVIDER="openai-compatible"
$env:PERSONAL_AGENT_TOOLKIT_BASE_URL="http://localhost:11434/v1"
$env:PERSONAL_AGENT_TOOLKIT_API_KEY="dummy"
$env:PERSONAL_AGENT_TOOLKIT_MODEL="your-model-name"
python -m personal_agent_toolkit
```

### One-off model override

```bash
python -m personal_agent_toolkit --model your-model-name
```

---

## Example command flow

```text
/agents
/agent coder
/plan-set Fix the build
/plan-add Inspect current failures
/grep TODO .
/note remember to simplify the parser later
/workflow capture-note release-checklist
```

---

## Key commands

- `/help`
- `/tools`
- `/plugins`
- `/workflows`
- `/workflow <name> [args...]`
- `/mcp-servers`
- `/mcp-resources [server]`
- `/mcp-read <uri>`
- `/note <text>`
- `/memory [limit]`
- `/memory-search <query>`
- `/skills`
- `/skill <name>`
- `/skill-show <name>`
- `/agents`
- `/agent <name>`
- `/model [name]`
- `/search <query>`
- `/plan`
- `/plan-set <title>`
- `/plan-add <step>`
- `/plan-done <step_id>`
- `/patch-preview <path> <old> <new>`
- `/replace-block <path> <old> <new>`
- `/insert-after <path> <anchor> <content>`

---

## Repository layout

```text
personal-agent-toolkit/
├─ personal_agent_toolkit/
│  ├─ agents/
│  └─ core/
├─ plugins/
├─ mcp_servers/
├─ skills/
├─ tests/
├─ .github/
├─ README.md
├─ ARCHITECTURE.md
├─ ROADMAP.md
├─ CHANGELOG.md
└─ pyproject.toml
```

---

## Open source and collaboration

This repository is intended to support:

- personal use
- collaborative enhancement
- research experiments
- independent plugin and workflow development

The project uses the **MIT License**.

Related docs:

- [LICENSE](LICENSE)
- [CONTRIBUTING.md](CONTRIBUTING.md)
- [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)
- [SECURITY.md](SECURITY.md)
- [ARCHITECTURE.md](ARCHITECTURE.md)
- [ROADMAP.md](ROADMAP.md)
- [CHANGELOG.md](CHANGELOG.md)

The repository also includes:

- GitHub Actions CI
- issue templates
- pull request template

---

## Practical publishing notes

- keep secrets and personal data out of commits
- review prompts and plugin text before publishing
- keep branding neutral if you want lower trademark risk
- this repository intentionally avoids bundling mirrored upstream source trees

See also:

- [LEGAL_AND_PRIVACY.md](LEGAL_AND_PRIVACY.md)

---

## Verification

```bash
python -m unittest discover -s tests -v
python -m compileall personal_agent_toolkit
```
