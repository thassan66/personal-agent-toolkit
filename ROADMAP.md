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
- persistent statusline-style session context near the prompt
- public reasoning mode
- active-request cancellation with `Ctrl+C`
- workspace-local config file support
- health/provider/model inspection commands
- runtime controls for provider, reasoning, stream, and timeout
- best-effort readline history/completion
- npm launcher packaging

## Near-term goals

1. richer `/doctor` output and repair guidance
2. better task control commands like `/tasks --watch` and task filtering
3. cleaner markdown/section rendering for long answers
4. saved sessions and resumable conversations
5. prompt templates for common workflows

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
