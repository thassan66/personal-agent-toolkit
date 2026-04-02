# Security

## Reporting

If you find a security issue, do not post exploit details publicly in an issue first.

Instead, contact the maintainer privately and include:

- affected area
- reproduction steps
- potential impact
- suggested mitigation if available

## Scope

This project is local-first, but security still matters because it can:

- execute shell commands
- edit files
- load plugins
- run workflows

Please review contributions carefully for:

- command injection
- unsafe file operations
- accidental data exposure
- unsafe plugin behavior
- dangerous defaults
