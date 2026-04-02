# Contributing to Personal Agent Toolkit

Thanks for your interest in improving Personal Agent Toolkit.

## What this project welcomes

- personal-use improvements
- research experiments
- bug fixes
- documentation improvements
- new local-first workflows
- safer file/tooling behavior
- better testing and verification

## Good first contributions

- improve README examples
- add tests for commands/tools
- improve plugin examples
- improve skill prompts
- improve error messages
- add small local automation helpers

## Contribution guidelines

1. Keep changes small and reviewable.
2. Prefer local-first, privacy-respecting behavior.
3. Avoid adding unnecessary dependencies.
4. Add tests for behavior changes when practical.
5. Update docs when adding new commands, tools, or workflows.
6. Do not commit secrets, tokens, transcripts, or personal data.

## Development

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .
python -m unittest discover -s tests -v
```

## Pull request checklist

- [ ] code runs locally
- [ ] tests pass
- [ ] docs updated if needed
- [ ] no secrets or personal data added
- [ ] change is consistent with local-first scope

## Discussion themes

This repository is especially open to:

- personal agent workflows
- local research tooling
- prompt/skill systems
- lightweight plugin architectures
- safe automation and planning UX
