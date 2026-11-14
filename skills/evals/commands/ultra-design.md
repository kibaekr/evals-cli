# ultra-design

Eight genuinely different first takes on one visual brief, each from a different model family with its own tools, so the user sees the range before committing: brand and logo directions, landing pages, app screens, ads, thumbnails, short videos, small sites or games.

## 1. Brief and inputs

- Take the brief word for word (`rules.md`). If it depends on files (a current logo, brand guide, screenshots, product photos), upload them with `upload` and pass each ID with `--input`. Attach a file rather than describing it.

## 2. Setups

Size: 8, or 4 with `--quick`, or the user's number.

1. Run `suggest --prompt-file brief.md --count N` (with the same `--input` IDs) and save its JSON. It is the lineup Evals' Battle picks for this brief, with a reason for each setup. Use it unless the user named models.
2. If `suggest` is unavailable or the user named models, build the lineup yourself from `models` and `models --gen-ai`: one model per lab, and for images or video either `gen=auto` (each agent picks its own tools) or a different Gen AI tool per setup. Keep `skill=auto` unless the user named a skill.

## 3. Prepare, review, start

```sh
evals prepare --private --prompt-file brief.md --suggestion suggestion.json [--input ID ...]
# or, with your own lineup:
evals prepare --private --prompt-file brief.md \
  --setup "model=MODEL_A,gen=auto" --setup "model=MODEL_B,gen=auto" ...
```

Review with the user as `rules.md` says, one line per setup with why it is in the lineup. Start only on approval.

## 4. Results

Give the run link at once. Visual runs can take from minutes to hours; offer to wait (`wait RUN_ID --timeout 600`, repeated) or check back later. When setups finish, run `results RUN_ID --out .evals/RUN_ID` and give one line per setup: model and Gen AI tool, state, time if recorded, and the path of its main file. Show images or rendered pages when the host can display them.

Do not rank the takes yourself unless asked. Offer `ultra-judge` for a blind council verdict, or `continue` to push one direction further.
