# ultra-deck

Eight decks from one brief, each by a different model family: sales decks, marketing plans, pitch decks, board updates, strategy reviews. The user picks the strongest or combines the best slides.

## 1. Brief and inputs

- Take the brief word for word (`rules.md`). Decks live on their source material: upload the memo, notes, metrics, past deck, brand guide or logo with `upload` and pass each ID with `--input` (10 at most).
- If the brief does not say the format, ask once whether they want PowerPoint, PDF or a web page, and add their answer to the brief in their words. Do not choose for them.

## 2. Setups

Size: 8, or 4 with `--quick`. Use `suggest` as `ultra-design` does, or build the lineup yourself: one strong model per lab, `skill=auto`. Use `gen=auto` when the deck needs pictures (product shots, illustrations), otherwise leave Gen AI off.

## 3. Prepare, review, start

```sh
evals prepare --private --prompt-file brief.md --input MEMO_ID \
  --setup "model=MODEL_A" --setup "model=MODEL_B" ...
```

Decks usually carry company facts: default to Private and say so in the review. Start only on approval.

## 4. Results

Give the run link. When the setups finish, `results RUN_ID --out .evals/RUN_ID` and list each deck file by setup, with state and time. Read each deck's text in full before saying anything about it. Offer `ultra-judge` with a rubric the user cares about (clarity of the ask, story, evidence, design), or `continue` on the favourite with their edits.
