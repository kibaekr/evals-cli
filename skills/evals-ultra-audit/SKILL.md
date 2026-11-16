---
name: evals-ultra-audit
description: >-
  Reviews recent Claude Code and Codex sessions locally, finds where the user repeated work or had
  to correct results, and proposes experiments with models and catalog skills on their real briefs.
  Use when the user says "use evals ultra audit", "/evals-ultra-audit", or asks what could improve
  in their AI sessions.
argument-hint: "[--quick] [--private|--public] <brief>"
---

# evals ultra-audit

What the user typed: `$ARGUMENTS`

This command is part of the Evals skill, which lives in the `evals` folder next to this one (`../evals` from this file).

1. Read `../evals/rules.md`. It has the CLI and the rules every command follows.
2. Read `../evals/commands/ultra-audit.md` and follow it, with the text above as the brief.

If `../evals` is missing, tell the user the Evals skill is installed incompletely and to install the whole skills folder from https://github.com/kibaekr/evals-cli.
