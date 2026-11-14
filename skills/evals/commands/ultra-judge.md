# ultra-judge

A council of eight models from different families scores the same candidates blind against one rubric, each on its own, and the CLI tallies their votes. For subjective work where one model's taste is not enough: designs, brand directions, ads, copy, decks, videos, or the results of an earlier Evals run.

## 1. Candidates, blind

- Collect the candidates: local files or folders, or a run's results (`results RUN_ID --out .evals/RUN_ID`).
- Make them blind. Copy each into `.evals/judge-DATE/candidates/` as `A.ext`, `B.ext`, `C.ext` in shuffled order, with no names, model labels or watermarks in file names or metadata you control. Write the mapping to `.evals/judge-DATE/key.json` as `{"A": "original name or setup", ...}`. The key never leaves the machine.
- `upload` the candidates and keep their input IDs. A run takes 10 inputs at most; split a larger set into groups and say so.

## 2. Rubric

Use the user's rubric if they gave one. Otherwise propose 3 to 6 criteria that fit the work (for an ad: stops the scroll, clarity of the offer, brand fit, craft), each scored 0 to 10, with weights adding up to 100. Save the weights as `weights.json` (`{"criterion": weight, ...}`). Show the rubric in the review; the user can change it.

## 3. The judge brief

Every judge gets the identical brief:

```text
You are one judge on a panel. Score the attached candidates (files A, B, C, ...) against this rubric. Judge only what is in the files. Do not guess who made them.

RUBRIC
<each criterion, what it means, 0-10 anchors>

Write verdict.json, and nothing else, in exactly this shape:
{"scores": {"A": {"<criterion>": 0, ...}, "B": {...}}, "winner": "A", "reasons": {"A": "one sentence", "B": "one sentence"}}
```

## 4. Council

Size: 8 judges, or 4 with `--quick`. A different model per judge, one per lab, `gen=none`, `skill=none`, `effort=high`. Private by default: candidates are often unreleased work.

```sh
evals prepare --visibility private --prompt-file judge-brief.md \
  --input ID_A --input ID_B --input ID_C \
  --setup "model=JUDGE_1,gen=none,skill=none,effort=high" ...
```

Review and start as `rules.md` says.

## 5. Tally

When the judges finish:

```sh
evals results RUN_ID --out .evals/judge-DATE/verdicts
evals tally .evals/judge-DATE/verdicts --key .evals/judge-DATE/key.json --weights .evals/judge-DATE/weights.json
```

`tally` does arithmetic only: each judge's weighted score per candidate, the mean, first-place votes and the spread between judges. It names any judge whose `verdict.json` is missing or malformed; read that judge's `final_message.md` yourself and report what it said.

Report a table with the real names from the key: mean score, first-place votes and how much the judges agreed. Quote each judge's one-sentence reason for its winner, attributed to that judge. Say plainly when the council split. The council is a second opinion, not a verdict.
