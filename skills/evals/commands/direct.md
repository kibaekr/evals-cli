# direct

One model on one brief, then keep working on it, as the composer's Direct mode does. Use it when the user already knows which model they want and only wants Evals' workspace, tools and record.

1. Take the brief word for word and the model the user named (resolve it with `models`). Upload any files it needs and pass them with `--input`.
2. Prepare one setup: `evals prepare --private --prompt-file brief.md --setup "model=MODEL,gen=auto,skill=auto"`. Use `gen=none` when the brief needs no images, video or audio, and `runtime=native` for a ChatGPT-connected model when `models` shows `native_codex: true`.
3. Review and start as `rules.md` says.
4. Give the run link. When it finishes, `results RUN_ID --out .evals/RUN_ID` and show what it made. For changes, use `continue` with the user's words; if it produced nothing, offer `retry`.
