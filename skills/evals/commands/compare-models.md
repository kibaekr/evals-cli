# compare-models

Which model does this job best? The same brief, inputs and settings on several models; only the model changes.

## 1. Which models

- **The user named them** ("Opus vs GPT-6.1 Sol vs Gemini"): resolve each name to an ID with `models`. If a name matches more than one, ask which.
- **The user did not name them:** run `suggest --prompt-file brief.md --count N` (with the same `--input` IDs). Evals' Battle planner proposes a lineup for this brief: it reads what the brief is trying to do and favours the newest models in the catalog. Show its reason and each pick's reason.
- **The user named some and wants Evals to fill the rest:** take theirs, then add picks from `suggest` that are not already in the lineup.

Size: the number of models named, otherwise 4, or 8 if the user asks for a wide comparison.

## 2. Hold everything else fixed

Every setup gets the same skill choice (`skill=auto` unless the user said otherwise), the same Gen AI choice (`gen=none`, or `gen=auto` for all when the brief needs images or video) and the same effort level where each model offers it. Each model runs in its own maker's agent where it can: Claude models on a connected Claude account already do, and ChatGPT-connected models do with `runtime=native` when `models` shows `native_codex: true`. Say in the review which agent each setup runs in. A Battle suggestion may also pick a different Gen AI tool or skill per setup; for a model comparison, keep only its models and rebuild the lineup with identical settings:

```sh
evals prepare --private --prompt-file brief.md \
  --setup "model=MODEL_A,gen=none,skill=auto,effort=high" \
  --setup "model=MODEL_B,gen=none,skill=auto,effort=high" ...
```

If the user wants Battle's full picks instead (tools and skills too), use `--suggestion suggestion.json` and say that more than the model varies.

In the review, name what varies (the model) and what is held fixed. Start only on approval.

## 3. Results

Give the run link. When the setups finish, `results RUN_ID --out .evals/RUN_ID`, read every result in full, and report per model: what it made, state, time and charge where recorded. One run is one sample: say so before calling a model "better". Offer `ultra-judge` on the results for a blind council verdict.
