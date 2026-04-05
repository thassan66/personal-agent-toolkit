# Roadmap

## Current state

Implemented:

- local CLI/REPL agent runtime
- Anthropic + OpenAI-compatible providers
- native Ollama provider path
- tools, commands, memory, plans, skills
- lightweight plugins and workflows
- local MCP-style resource registry
- subagent delegation/spawn/wait
- operator-style HUD, progress feed, and streaming output
- public reasoning mode
- active-request cancellation with `Ctrl+C`
- npm launcher packaging

## Near-term goals

1. configuration file support
2. `/doctor` or `/health` command for provider/model setup checks
3. persistent footer/statusline
4. command completion and richer history UX
5. better task control commands like `/cancel`, `/tasks --watch`, and `/task-clear`

## Mid-term goals

- richer planning/task graph support
- safer file-edit workflows
- stronger model/provider abstractions
- better logs/trace/debug tooling
- optional semantic memory/search
- model capability matrix and smarter provider/model recommendations

## Longer-term ideas

- richer TUI experience
- remote execution backends
- distributed or team-agent workflows
- stronger plugin lifecycle APIs
- more provider adapters

## Contribution opportunities

Good areas for contributors:

- documentation
- tests
- provider integrations
- plugins
- skills
- local workflow UX
