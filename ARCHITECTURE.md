# Architecture

## Overview

Personal Agent Toolkit is a local-first Python agent runtime organized around a few simple layers:

- **providers** — talk to LLM backends
- **query engine** — coordinates prompts, tools, and responses
- **tools** — structured capabilities such as file I/O, search, shell, planning, memory, and workflows
- **commands** — human-facing slash commands layered over the tool system
- **plugins** — lightweight extension points defined by JSON manifests
- **skills** — markdown-based prompt overlays for task-specific behavior
- **memory / planning** — simple persistent local state
- **MCP-style resources** — lightweight local documentation/resource registry

## Main runtime flow

1. CLI starts in `personal_agent_toolkit/__main__.py`
2. Provider, tools, commands, plugins, skills, memory, plan store, and MCP registry are initialized
3. `QueryEngine` receives user input
4. Slash commands are handled directly by `CommandRegistry`
5. Non-command prompts go through the active provider
6. If the provider returns tool calls, the engine executes them and feeds results back into the conversation

## Key modules

### `personal_agent_toolkit/core/query_engine.py`
- central conversation loop
- attaches system prompts, active skills, memory summaries, and plan context
- handles tool-call round-trips

### `personal_agent_toolkit/core/providers.py`
- `EchoProvider`
- `OpenAICompatibleProvider`
- `AnthropicProvider`

### `personal_agent_toolkit/core/tools.py`
- tool definitions
- tool execution
- tool schemas for provider-facing tool use

### `personal_agent_toolkit/core/builtin_tools.py`
- file operations
- shell command execution
- search/grep/glob
- memory/skills/discovery
- MCP resource access
- workflow execution
- planning helpers
- subagent orchestration

### `personal_agent_toolkit/core/builtin_commands.py`
- slash-command UX surface
- maps user-friendly commands onto tools and state

### `personal_agent_toolkit/core/plugins.py`
- JSON-manifest plugin loader
- plugin commands/tools
- plugin hooks
- plugin workflows

### `personal_agent_toolkit/core/skills.py`
- markdown skill loader
- task-oriented prompt overlays

### `personal_agent_toolkit/core/memory.py`
- local JSONL note persistence

### `personal_agent_toolkit/core/planning.py`
- local JSON plan persistence

## Persistence

Local state files:

- `.personal_agent_toolkit_memory.jsonl`
- `.personal_agent_toolkit_plan.json`

These are ignored by git and intended for local use only.

## Extension model

### Plugins
Plugins live in `plugins/*.json` and can define:

- commands
- tools
- hooks
- workflows

### Skills
Skills live in `skills/*.md` and can be activated dynamically during a session.

### MCP-style resources
MCP-style resource manifests live in `mcp_servers/*.json`.

## Design goals

- local-first
- low dependency complexity
- easy to understand and extend
- safe default workspace behavior
- useful for personal use, research, and open collaboration
