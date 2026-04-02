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

## Model and provider configuration

Yes — you can use this toolkit with different LLMs.

### What is supported right now

The current runtime supports:

- `echo` provider for testing
- any **OpenAI-compatible chat completions API**

That means you can use:

- local models served behind an OpenAI-compatible endpoint
- hosted models exposed through an OpenAI-compatible gateway
- any provider that accepts `POST /chat/completions` in OpenAI-style format

### Current limitation

There is **not** a native Anthropic/Claude provider in the code right now.

So for Claude, you need one of these:

- an OpenAI-compatible gateway/proxy that routes to Claude
- a hosted platform exposing Claude through an OpenAI-compatible API surface

### Environment variables

The runtime reads these variables:

```bash
PERSONAL_AGENT_TOOLKIT_PROVIDER
PERSONAL_AGENT_TOOLKIT_BASE_URL
PERSONAL_AGENT_TOOLKIT_API_KEY
PERSONAL_AGENT_TOOLKIT_MODEL
PERSONAL_AGENT_TOOLKIT_TIMEOUT
PERSONAL_AGENT_TOOLKIT_DEBUG
```

### Provider values

Use:

```bash
PERSONAL_AGENT_TOOLKIT_PROVIDER=echo
```

or

```bash
PERSONAL_AGENT_TOOLKIT_PROVIDER=openai
```

### Example: local OpenAI-compatible server

```bash
set PERSONAL_AGENT_TOOLKIT_PROVIDER=openai
set PERSONAL_AGENT_TOOLKIT_BASE_URL=http://localhost:11434/v1
set PERSONAL_AGENT_TOOLKIT_API_KEY=dummy
set PERSONAL_AGENT_TOOLKIT_MODEL=qwen2.5-coder
python -m personal_agent_toolkit
```

### Example: one-off model override

```bash
python -m personal_agent_toolkit --model qwen2.5-coder
```

### Example: debug mode

```bash
set PERSONAL_AGENT_TOOLKIT_DEBUG=1
python -m personal_agent_toolkit
```

### Practical guidance

- use `echo` first to confirm the runtime works
- switch to `openai` once your endpoint is ready
- pass the model with `PERSONAL_AGENT_TOOLKIT_MODEL` or `--model`
- if tools do not work with a provider, confirm the provider supports OpenAI-style tool calling

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

## Verification

```bash
python -m unittest discover -s tests -v
python -m compileall personal_agent_toolkit
```
