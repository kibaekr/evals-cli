# ultra-audit

Read the user's own recent Claude Code and Codex sessions, report what they actually use AI for, and propose ultra runs on their real briefs: a cheaper model that may do as well, a stronger one that may do better, a better Gen AI tool for their visual work. Nothing leaves the machine until the user approves a specific brief.

## 1. List the sessions

```sh
evals sessions --days 7 --out ~/.config/evals/audit/DATE
```

Use `--days 3` with `--quick`, or the period the user names (a busy month can run to hundreds of millions of characters, so say what a longer period means before reading it). It reads `~/.claude/projects` and `~/.codex/sessions` and uploads nothing. It writes one JSON file per session (tool, project folder, title, start and end, models used, token totals, tool calls by name including Gen AI tools, files written, and every user-role message word for word with its `source` label; an identical message sent again is kept once with `repeats` and every time it was sent) plus `index.json` with one row per session and its first message.

User-role messages include ones no person typed: automation prompts, system reminders, compaction summaries, command echoes. The labels differ by app (the desktop app records typed messages as `sdk`). Deciding which messages a person wrote is part of the reading below, not something to filter by label.

## 2. Read the sessions

1. **Triage every session.** Give `index.json` to sub-agents in groups (a small, fast model is fine). For each row they decide, from its title, folder, models, tools and first message, whether the session may hold creative, subjective or research work. Every row gets a decision.
2. **Read the likely ones in full.** Give each of those session files to a sub-agent. For the session it reads, it answers:
   - Which messages did a person write, and is there creative, subjective or research work in them: design, branding, decks, copy, images, video, audio, sites, research, plans or strategy? Engineering counts only when the result is judged by taste (a landing page, UI copy).
   - If so: the job in a few words, the person's brief word for word (the message that asked for the work, plus follow-ups that changed it), the model or Gen AI tool that did it, the tokens, and whether files came out.

Merge every reply. Report how many sessions were triaged, how many were read in full, and how many could not be read and why.

## 3. Report

Like Claude Code's `/insights`, but about the work: the period, sessions triaged and read in full; the jobs ranked by how often they came up and how many tokens they used; which models and Gen AI tools did each job; anything notable, such as one job always on the most expensive model.

## 4. Propose experiments

One to three, ranked by likely payoff (how often the job comes up times what it costs). For each:

- **The job** and why it is worth testing.
- **The brief:** one real recent brief from the sessions, word for word, with the files it used.
- **The command:** usually `ultra-design`, `ultra-deck` or `ultra-research` with the model they use in the lineup; `compare` for a straight cheaper-or-not question; `ultra-judge` when they kept choosing between versions by hand.
- **What it would show:** for example "whether Sonnet matches Opus on your pitch decks".

## 5. Privacy

These briefs come from private sessions. Before anything is uploaded, show each chosen brief and file list in full, point out anything that looks like a secret, client name or personal detail, and let the user edit or drop it. Use Private. If only Public is available, accept only a clear yes.

## 6. Run and close the loop

On approval, follow that command's file. When results are in, state the finding as evidence about that brief ("on this deck brief, Sonnet's version matched Opus's at a third of the tokens"), not as a general rule, and say it is one sample. If the evidence supports a change, suggest it; switching is the user's call.
