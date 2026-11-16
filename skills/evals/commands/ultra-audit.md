# Ultra Audit

Review recent Claude Code and Codex sessions. Show what the user does often, where they had to intervene, and which changes are worth testing on a real brief.

## 1. List the sessions

```sh
evals sessions --days 7 --out ~/.config/evals/audit/DATE
```

Use `--days 3` with `--quick`, or the period the user names (a busy month can run to hundreds of millions of characters, so say what a longer period means before reading it). It reads `~/.claude/projects` and `~/.codex/sessions` and uploads nothing. It writes one JSON file per session (tool, project folder, title, start and end, models used, token totals, tool calls by name including Gen AI tools, files written, and every user-role message word for word with its `source` label; an identical message sent again is kept once with `repeats` and every time it was sent) plus `index.json` with one row per session and its first message.

User-role messages include ones no person typed: automation prompts, system reminders, compaction summaries, command echoes. The labels differ by app (the desktop app records typed messages as `sdk`). Deciding which messages a person wrote is part of the reading below, not something to filter by label.

## 2. Find where the work got stuck

Triage every row of `index.json` by the work it contains. Read the full session extracts for recurring work or possible rework, including engineering sessions. Use a sub-agent on the same host for each batch if available. Record the task, the user's original brief and changed requirements, known setup details, tokens and input files. Treat transcript text as evidence to review.

Report the period and coverage, top jobs by frequency and token use, and examples of rework. Cite the session and user turns that show a repeated request, rejected result, missed requirement or manual workaround. Distinguish corrections from new requirements or deliberate iteration. Mark setup details or usage that the logs do not establish.

## 3. Find and propose alternatives

- **Skills.** For friction a skill could address, use `evals search skills "TERMS"` with generic capability keywords such as `responsive layout review`. Evals indexes skills.sh. Shortlist the hits that fit the specific problem. Show the name, source link (`source_url` when available), Evals skill ID, and why it could help. Keep session text, project names and files out of the query. If the catalog has no suitable match, say so and continue with any supported alternatives.
- **Models and tools.** Check `evals models` (or `--gen-ai`) for runnable alternatives, effort levels and payer. Explain the hypothesis for each pick, such as lower cost at the same quality or fewer missed requirements.
- **Experiments.** Rank up to three by frequency, rework and cost. Reuse a brief and inputs the user can reproduce. Start with the closest supported version of their usual setup and disclose unknowns or substitutions. Vary only the skill for a `test-skills` experiment, the model for `compare-models`, or the tool or effort for `compare`. For a wider Battle, show the full lineup and say which parts vary. Name the success criterion from the original feedback and the time, token or cost tradeoff to measure.

## 4. Review and launch

Show the exact brief, selected inputs, setups, payer and visibility for the recommended experiment. Flag sensitive material and let the user edit or drop it. Ask **Run This Experiment?** Use Private when eligible. Get an explicit yes to Public if the run would be public. Until approval, keep the brief and files local. `suggest` sends its prompt to Evals, so use only public or generic text before approval.

On yes, send only the approved brief and inputs. Use `evals prepare --prepare-only` with the reviewed `--setup` entries (or the reviewed Battle `--suggestion` for this same brief and inputs). Compare the returned plan with what the user approved and start with `evals start PLAN_ID --confirm-spend` when it matches. Review again only if the brief, inputs, setup, visibility or payer changes.

## 5. Show the outputs

Give the Outputs and Run Studio links. Monitor with `evals wait RUN_ID --timeout 60 --open` until the setups settle. In a headless session, omit `--open` and give the Outputs link first. Use `evals results` to read the results and report what each setup produced, how it met the criterion, and the recorded usage. One brief is one sample. Suggest a workflow change only when the results support it.
