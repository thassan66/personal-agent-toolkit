# Local Model Setup

This toolkit already supports local OpenAI-compatible backends. The easiest private setup is `ollama`.

## Recommended local profiles

- `balanced` -> `qwen2.5-coder:14b`
- `reasoning` -> `deepseek-r1:14b`
- `agentic` -> `devstral:24b`

The CLI now resolves these profiles against installed Ollama models when possible. For example, if `qwen2.5-coder:14b` is not installed but `qwen2.5-coder:3b` is, `--local-profile balanced` can fall back to the installed model automatically.

These are practical starting points for day-to-day coding:

- `qwen2.5-coder:14b` is a good default when you want strong coding quality without a very large local footprint.
- `deepseek-r1:14b` is better when you want heavier step-by-step reasoning and debugging.
- `devstral:24b` is useful when you want stronger repo navigation and multi-step coding-agent behavior.

## Fastest path on Windows

Install Ollama, then run:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup-local-agent.ps1 -Profile balanced -Pull
```

Switch profiles:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup-local-agent.ps1 -Profile reasoning
powershell -ExecutionPolicy Bypass -File .\scripts\setup-local-agent.ps1 -Profile agentic
```

## Direct CLI usage

You can also skip the helper script and run the CLI directly:

```powershell
python -m personal_agent_toolkit --provider ollama --local-profile balanced
python -m personal_agent_toolkit --provider ollama --local-profile reasoning
python -m personal_agent_toolkit --provider ollama --local-profile agentic
```

If you installed the npm wrapper instead of the Python entrypoint:

```powershell
personal-agent-toolkit --provider ollama --local-profile balanced
personal-agent-toolkit --provider ollama --local-profile reasoning --public-reasoning
```

The npm package is a launcher for the Python CLI, so Python 3.11+ is still required.

For a more transparent interactive experience:

```powershell
python -m personal_agent_toolkit --provider ollama --local-profile balanced --public-reasoning
python -m personal_agent_toolkit --provider ollama --local-profile reasoning --public-reasoning
```

Recommended by use case:

- fastest responses: `--model qwen2.5-coder:3b`
- best interactive balance: `--local-profile balanced --public-reasoning`
- deeper planning/reasoning: `--local-profile reasoning --public-reasoning`

If you use another local OpenAI-style server, the CLI now exposes direct provider flags too:

```powershell
python -m personal_agent_toolkit --provider lm-studio --model qwen2.5-coder:14b
python -m personal_agent_toolkit --provider llama.cpp --base-url http://localhost:8080/v1 --model qwen2.5-coder:14b
```

## Privacy notes

- Requests stay on your machine when you point the toolkit at a local model server.
- Repo files, plans, notes, and memory stay in the local workspace unless you explicitly connect to a hosted provider.
- You should still review local model server logs and keep sensitive repos off telemetry-enabled tooling.

## Notes on responsiveness

- `deepseek-r1:14b` can be much slower to first token than the qwen coder models.
- For interactive terminal use, `qwen2.5-coder:3b` or `qwen2.5-coder:14b` may feel better than `deepseek-r1:14b`.
- `Ctrl+C` now cancels the active request while keeping the REPL open.
