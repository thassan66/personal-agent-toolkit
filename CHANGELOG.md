# Changelog

## Unreleased

- improved the CLI HUD, prompt, and progress feed
- added `/status` and `/clear`
- added public reasoning mode via `--public-reasoning`
- added live streaming output for OpenAI-compatible providers
- added automatic fallback for models that do not support tool calling
- added clearer provider error messages for auth, timeout, and missing-model cases
- added installed-model-aware Ollama local-profile resolution
- added in-session `Ctrl+C` cancellation for the active request

## 0.1.0

Initial public-ready release.

Included:

- local-first Python agent runtime
- Anthropic and OpenAI-compatible providers
- slash commands and built-in tools
- planning and memory
- skills
- plugins and workflows
- local MCP-style resources
- tests and contributor docs
