<div align="center">

# Personal Agent Toolkit

**A local-first toolkit for building and running personal coding agents**

![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Tests](https://img.shields.io/badge/tests-passing-brightgreen)
![Scope](https://img.shields.io/badge/scope-local--first-orange)
![Status](https://img.shields.io/badge/status-public--ready-success)

</div>

Personal Agent Toolkit is an independent, generic personal-agent toolkit for local automation.
It is structured to be publishable as its own GitHub repository.

> Package name: `personal_agent_toolkit`  
> CLI command: `personal-agent-toolkit`

## Open-source and collaboration friendly

This repository is intended to be open source and welcoming for:

- personal use
- collaborative enhancement
- research experiments
- independent extensions and plugins

The project currently uses the **MIT License**, which is permissive and suitable for open collaboration.

Related docs:

- [LICENSE](LICENSE)
- [CONTRIBUTING.md](CONTRIBUTING.md)
- [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)
- [SECURITY.md](SECURITY.md)
- [ARCHITECTURE.md](ARCHITECTURE.md)
- [ROADMAP.md](ROADMAP.md)
- [CHANGELOG.md](CHANGELOG.md)

## Important publishing notes

- This repository is intentionally branded with neutral names.
- The exported package does **not** include the mirrored upstream stub tree.
- It is presented as an independent implementation for local agent workflows.
- Review names, prompts, and sample assets again before publishing if you want stricter branding separation.

## Features

- local CLI/REPL agent runtime
- tools for file operations, shell execution, search, diffs, and patch previews
- lightweight plugins and workflows
- lightweight local MCP-style resources
- persistent notes and plans
- markdown-based skills
- in-process delegate/spawn/wait subagents

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
├─ README.md
├─ ARCHITECTURE.md
├─ ROADMAP.md
├─ CHANGELOG.md
└─ pyproject.toml
```

## Install

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .
```

## Run

```bash
python -m personal_agent_toolkit
```

Single prompt:

```bash
python -m personal_agent_toolkit --prompt "/help"
```

## Model, provider, and agent configuration

Yes - you can use this toolkit with different models.

### What is supported right now

The current runtime supports:

- `echo` for local smoke testing
- native `anthropic` / `claude` provider
- any **OpenAI-compatible chat completions API**

That means you can connect the toolkit to:

- Anthropic Claude through the native Messages API
- local model servers such as Ollama
- hosted OpenAI-compatible gateways
- proxy layers that expose non-OpenAI models through `/chat/completions`

### Claude and other non-OpenAI models

Claude is now supported natively through the Anthropic Messages API.

Other models still work well if they are served through an OpenAI-compatible endpoint.

### Environment variables

The runtime reads these variables:

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

Supported provider values:

- `echo`
- `anthropic`
- `claude`
- `openai`
- `openai-compatible`

### Example: connect to Anthropic Claude natively

PowerShell:

```powershell
$env:PERSONAL_AGENT_TOOLKIT_PROVIDER="anthropic"
$env:PERSONAL_AGENT_TOOLKIT_API_KEY="your-anthropic-api-key"
$env:PERSONAL_AGENT_TOOLKIT_MODEL="claude-sonnet-4-5"
python -m personal_agent_toolkit
```

CMD:

```bat
set PERSONAL_AGENT_TOOLKIT_PROVIDER=anthropic
set PERSONAL_AGENT_TOOLKIT_API_KEY=your-anthropic-api-key
set PERSONAL_AGENT_TOOLKIT_MODEL=claude-sonnet-4-5
python -m personal_agent_toolkit
```

Optional:

```powershell
$env:PERSONAL_AGENT_TOOLKIT_ANTHROPIC_VERSION="2023-06-01"
$env:PERSONAL_AGENT_TOOLKIT_MAX_TOKENS="4096"
```

### Example: connect to an OpenAI-compatible endpoint

PowerShell:

```powershell
$env:PERSONAL_AGENT_TOOLKIT_PROVIDER="openai-compatible"
$env:PERSONAL_AGENT_TOOLKIT_BASE_URL="http://localhost:11434/v1"
$env:PERSONAL_AGENT_TOOLKIT_API_KEY="dummy"
$env:PERSONAL_AGENT_TOOLKIT_MODEL="your-model-name"
python -m personal_agent_toolkit
```

CMD:

```bat
set PERSONAL_AGENT_TOOLKIT_PROVIDER=openai-compatible
set PERSONAL_AGENT_TOOLKIT_BASE_URL=http://localhost:11434/v1
set PERSONAL_AGENT_TOOLKIT_API_KEY=dummy
set PERSONAL_AGENT_TOOLKIT_MODEL=your-model-name
python -m personal_agent_toolkit
```

### One-off model override

```bash
python -m personal_agent_toolkit --model your-model-name
```

### Change the active model or agent in the REPL

These runtime commands are built in:

- `/agents` - list available agent profiles
- `/agent <name>` - switch to a profile such as `coder`, `planner`, or `reviewer`
- `/model` - show the current model
- `/model <name>` - switch models without restarting

Example:

```text
/agents
/agent coder
/model your-model-name
```

### Customize agent profiles

Agent profiles live in `personal_agent_toolkit/agents/*.json`.
Each profile can set:

- `name`
- `description`
- `model`
- `system_prompt`

Example:

```json
{
  "name": "claude-coder",
  "description": "Coding agent routed through a Claude-compatible gateway",
  "model": "your-claude-compatible-model-name",
  "system_prompt": "You are a coding-focused personal agent. Prefer concrete code changes and clear summaries."
}
```

After adding the file, start the CLI and run:

```text
/agent claude-coder
```

This is the easiest way to keep different prompts and default models for different task types.

### Practical guidance

- start with `echo` to confirm the runtime works
- use `anthropic` for native Claude access
- use `openai-compatible` for local gateways and compatible providers
- set a default with `PERSONAL_AGENT_TOOLKIT_MODEL` and override per session with `--model` or `/model`
- if tool calling fails, verify that your endpoint supports the required tool-calling format for that provider

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

## Repository hygiene

Before pushing to GitHub:

- confirm no secrets are present
- confirm no personal data is committed
- review sample prompts/plugin text for naming you do not want public
- choose the license you want to publish under

## Collaboration notes

If you publish this repo on GitHub, recommended next steps are:

- enable Issues
- enable Discussions
- protect the default branch
- require pull requests for non-trivial changes
- add CI once the repo is public

This repository now includes:

- GitHub Actions CI
- issue templates
- pull request template

## Verification

```bash
python -m unittest discover -s tests -v
python -m compileall personal_agent_toolkit
```
