---
name: evals-ultra-audit
description: >-
  Reads the user's recent Claude Code and Codex sessions locally, reports what they use AI for and on
  which models, and proposes Evals experiments on their real briefs to find what is cheaper or better.
  Use when the user says "use evals ultra audit", "/evals-ultra-audit", or asks how they use AI, what
  they overpay for, or which model to use for their recurring work.
argument-hint: "[--quick] [--private|--public] <brief>"
---

# evals ultra-audit

What the user typed: `$ARGUMENTS`

This command is part of the Evals skill, which lives in the `evals` folder next to this one (`../evals` from this file).

1. Read `../evals/rules.md`. It has the CLI and the rules every command follows.
2. Read `../evals/commands/ultra-audit.md` and follow it, with the text above as the brief.

If `../evals` is missing, tell the user the Evals skill is installed incompletely and to install the whole skills folder from https://github.com/kibaekr/evals-cli.
