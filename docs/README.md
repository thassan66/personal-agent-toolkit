# Docs assets

This folder contains public-facing documentation assets for the repository.

## Suggested demo assets

- `demo-startup.gif`
- `demo-workflow-memory.gif`
- `demo-editing.gif`
- `demo-hud-streaming.gif`

Current terminal-style demo assets in this repo can be regenerated with:

```powershell
python .\scripts\generate_demo_assets.py
```

You can record these with:

- terminal screen capture tools
- asciinema + GIF conversion
- OBS
- ScreenToGif

## Suggested captures

### `demo-startup.gif`
- start the CLI
- run `/status`
- run `/health`
- run `/agents`
- switch with `/agent coder`
- run `/help`
- trigger a long request and press `Ctrl+C`

### `demo-workflow-memory.gif`
- run `/workflow capture-note release-checklist`
- run `/memory`
- run `/memory-search release`

### `demo-editing.gif`
- run `/grep TODO .`
- run `/patch-preview ...`
- run `/replace-block ...`
- run `/diff ...`

### Suggested new capture: streaming / planning
- start with `--public-reasoning`
- run `/agent planner`
- ask for a short plan
- show `Reasoning summary:` and live streaming output

## Useful docs

- [Command Guide](command-guide.md)
- [Local model setup](local-model-setup.md)
- [Config examples](config-examples.md)
