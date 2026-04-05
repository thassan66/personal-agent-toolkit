# Config Examples

The CLI can load workspace-local defaults from `.personal-agent-toolkit.toml`.

CLI flags take precedence over environment variables, and environment variables take precedence over the config file.

## Ollama

```toml
provider = "ollama"
model = "qwen2.5-coder:14b"
timeout = 300
public_reasoning = true
stream = true
```

## Ollama reasoning profile

```toml
provider = "ollama"
local_profile = "reasoning"
timeout = 300
public_reasoning = true
stream = true
```

## Anthropic

```toml
provider = "anthropic"
model = "claude-sonnet-4-5"
timeout = 120
public_reasoning = true
```

Set the API key through `ANTHROPIC_API_KEY` or `PERSONAL_AGENT_TOOLKIT_API_KEY`.

## OpenAI-compatible

```toml
provider = "openai-compatible"
base_url = "http://localhost:11434/v1"
model = "your-model-name"
timeout = 120
stream = true
```
