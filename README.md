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

> Package name: `indie_agent_kit`  
> CLI command: `indie-agent-kit`

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
python -m indie_agent_kit
```

Single prompt:

```bash
python -m indie_agent_kit --prompt "/help"
```

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

## Verification

```bash
python -m unittest discover -s tests -v
python -m compileall indie_agent_kit
```
