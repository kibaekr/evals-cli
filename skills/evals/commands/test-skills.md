# test-skills

Does this skill make the work better? The same model, brief, inputs and settings with no skill (the control) and with the skill. Only the skill changes.

## 1. The skill

- Find the skill's ID with `search skills "NAME OR TERMS"` (non-confidential terms only). Several skills can be tested at once: one setup per skill, or one setup with several skills together (repeat `skill=` in the setup).
- A skill that lives only on the user's machine has to be on Evals first: ask the user to add it on Evals.ag by its link, then search again. Never upload a skill's files as an input instead; that is not the same as the agent running with the skill.

## 2. Setups

- **The model:** the one the user named, otherwise the model they normally use for this kind of work, otherwise a strong model their connected Claude or ChatGPT account covers (no Evals fee).
- **Control:** `skill=none`. **Test:** `skill=SKILL_ID` (or several). Everything else identical: the same `gen=` and `effort=` in every setup.
- One sample per side can mislead. With `--quick` run one control and one test; by default run two of each (the same setup twice), so the user can see how much a model varies on its own before crediting the skill.

```sh
evals prepare --visibility private --prompt-file brief.md \
  --setup "model=MODEL,gen=none,skill=none,effort=high" \
  --setup "model=MODEL,gen=none,skill=none,effort=high" \
  --setup "model=MODEL,gen=none,skill=SKILL_ID,effort=high" \
  --setup "model=MODEL,gen=none,skill=SKILL_ID,effort=high"
```

In the review, say which setups are the control and which carry the skill. Start only on approval.

## 3. Results

Give the run link. When the setups finish, `results RUN_ID --out .evals/RUN_ID` and read every result in full. Compare the skill setups with the controls: what the skill changed in the work, and whether the two controls already differed as much. Report time and charge where recorded. Offer `ultra-judge` for a blind verdict between control and skill outputs.
