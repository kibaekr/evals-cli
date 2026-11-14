# ultra-research

Eight agents from different model families investigate the same question independently, each on its own computer with web access, so less gets missed: competitors, market maps, business plans, due diligence, "find every X". Then you merge what they found and show where they agree and where they do not.

## 1. Brief

Take the question word for word and add this footer, identical for every agent, and show it in the review:

> Write your findings to `report.md`. Back every claim with the URL or document you took it from. Mark anything you could not verify as unverified. List the sources you checked that turned up nothing useful.

Upload files the question depends on (a deck to critique, a list to extend) and pass them with `--input`.

## 2. Setups

Size: 8, or 4 with `--quick`. The strongest available model from each lab, so their blind spots differ; `gen=none`, `skill=auto`, and the highest `effort` each model offers (see `models`). Prefer models a connected account covers when the choice is otherwise equal.

```sh
evals prepare --visibility private --prompt-file question.md \
  --setup "model=MODEL_A,gen=none,effort=high" --setup "model=MODEL_B,gen=none,effort=high" ...
```

Review and start as `rules.md` says.

## 3. Merge

When the agents finish, `results RUN_ID --out .evals/RUN_ID`. Read every report in full; if they are long, give each to its own sub-agent to list its claims with sources, then merge every reply. Write `.evals/RUN_ID/merged.md`:

1. **Agreed:** findings several agents reached on their own, with how many and their sources.
2. **Found by one:** findings only one agent reported, labelled with that agent. Do not promote them to consensus.
3. **Disagreements:** where agents contradict each other, both sides with sources.
4. **Gaps:** what the question asked that nobody answered, and anything marked unverified.

Give the user the merged report and the run link. Add no facts of your own; if you check a source yourself, say which.
