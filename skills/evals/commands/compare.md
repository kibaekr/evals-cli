# compare

A controlled test: change exactly one thing and hold everything else fixed, so a difference in the results comes from that one thing. For models use `compare-models`; for skills use `test-skills`. This file covers the rest: Gen AI tools and effort levels.

## 1. Find the one variable

| question | varies | fixed |
| --- | --- | --- |
| Which model is better for this? | `model=` | Gen AI tool, skills, effort, inputs |
| Does my skill help? | `skill=` (`none` against the skill) | model, Gen AI tool, effort, inputs |
| Which image or video tool fits? | `gen=` | model, skills, effort, inputs |
| Is a lower effort good enough? | `effort=` | model, Gen AI tool, skills, inputs |

If the user wants several things varied at once, say that it stops being a controlled test and offer an ultra command instead, or one compare per variable.

Size: 2, or one setup per value the user names, at most 8. Find model IDs with `models` (`--gen-ai` for tools) and skill IDs with `search skills "TERMS"` using non-confidential terms.

## 2. Prepare, review, start

Repeat the fixed parts in every `--setup` so nothing defaults differently:

```sh
evals prepare --visibility private --prompt-file brief.md \
  --setup "model=MODEL_ID,gen=none,skill=none,effort=high" \
  --setup "model=MODEL_ID,gen=none,skill=SKILL_ID,effort=high"
```

In the review, say in one sentence what varies and what is held fixed. Start only on approval.

## 3. Results

Give the run link. When the setups finish, `results RUN_ID --out .evals/RUN_ID`, read every result in full, and report the differences you can attribute to the variable, with time and charge per setup where recorded. One run is one sample: say so before calling anything "better". Offer `ultra-judge` on the results for a blind second opinion.
