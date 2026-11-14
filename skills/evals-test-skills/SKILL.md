---
name: evals-test-skills
description: >-
  A skill against a no-skill control on the same AI model, brief and inputs through Evals, so only the
  skill changes, with repeated controls to show how much the model varies on its own. Use when the
  user says "use evals test skills", "/evals-test-skills", or asks whether a skill actually helps.
argument-hint: "[--quick] [--private|--public] <brief>"
---

# evals test-skills

What the user typed: `$ARGUMENTS`

This command is part of the Evals skill, which lives in the `evals` folder next to this one (`../evals` from this file).

1. Read `../evals/rules.md`. It has the CLI and the rules every command follows.
2. Read `../evals/commands/test-skills.md` and follow it, with the text above as the brief.

If `../evals` is missing, tell the user the Evals skill is installed incompletely and to install the whole skills folder from https://github.com/kibaekr/evals-cli.
