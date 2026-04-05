# Command Guide

This is the first-class command reference for `personal_agent_toolkit`.

## Session / UI

- `/help` — show grouped command help
- `/help <command>` — show usage and example for one command
- `/status` — show current provider, model, agent, config, tasks, and plan summary
- `/clear` — clear the terminal and redraw the HUD
- `/history` — show recent message history
- `/quit` / `/exit` — leave the REPL

## Runtime controls

- `/provider` — show the active provider
- `/provider <name>` — switch provider
- `/provider-status` — show provider latency or config state
- `/model` — show the active model
- `/model <name>` — switch model
- `/reasoning` — show reasoning mode
- `/reasoning on|off` — toggle public reasoning summaries
- `/stream` — show streaming mode
- `/stream on|off` — toggle streaming output
- `/timeout` — show the active timeout
- `/timeout <seconds>` — set request timeout
- `/health` — run a basic environment/provider health check
- `/doctor` — run actionable diagnostics and setup guidance
- `/models` — list local Ollama models and mark recommended ones

## Agents / skills

- `/agents`
- `/agent [name]`
- `/skills`
- `/skill [name]`
- `/skill-show <name>`
- `/skill-clear`

## Workspace / editing

- `/pwd`
- `/ls [path] [--recursive]`
- `/read <path>`
- `/write <path> "<content>"`
- `/append <path> "<content>"`
- `/grep <pattern> [root]`
- `/glob <pattern>`
- `/run <command>`
- `/replace <path> <old> <new>`
- `/regex-replace <path> <pattern> <replacement>`
- `/patch-preview <path> <old> <new>`
- `/replace-block <path> <old> <new>`
- `/insert-after <path> <anchor> <content>`
- `/diff <path_a> <path_b>`

## Memory / planning

- `/note <text>`
- `/memory [limit]`
- `/memory-search <query>`
- `/plan`
- `/plan-set <title>`
- `/plan-add <step>`
- `/plan-done <step_id>`
- `/plan-clear`

## Tasks / workflows / tools

- `/tasks`
- `/task [task_id]`
- `/cancel [task_id]`
- `/task-clear`
- `/delegate <agent> <prompt>`
- `/spawn <agent> <prompt>`
- `/wait <task_id>`
- `/plugins`
- `/workflows`
- `/workflow <name> [args...]`
- `/mcp-servers`
- `/mcp-resources [server]`
- `/mcp-read <uri>`
- `/tools`
- `/tool <name> [json-args]`

## Important controls

- `Ctrl+C` — cancel the active foreground request and stay in the REPL
- `.personal-agent-toolkit.toml` — workspace config file

## Suggested starting commands

```text
/status
/health
/doctor
/models
/agent planner
```
