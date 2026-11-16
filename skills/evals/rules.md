# Evals: the CLI and the rules every command follows

## The CLI

Run the bundled script: `python3 "<the evals skill folder>/scripts/evals.py" <command>`. From an `evals-ultra-*` skill that folder is `../evals` next to it. Prefer the bundled script: an `evals` command on PATH may be another tool (npm's `evals` package installs one). Every command prints JSON; `--help` on any command lists its flags. Below, `evals X` means that script with command `X`.

| command | what it does |
| --- | --- |
| `whoami` | The connected account and whether Private runs are available. If it says to log in, start `evals login --no-browser` in the background and give the user the evals.ag link and device code it prints: they sign in there, or create a free account, and approve the code; the login finishes by itself within 5 minutes. Never read or ask for the credential file, and never approve a device for the user. |
| `models` | LLMs this account can run, with route and payer, and the effort levels each offers. |
| `models --gen-ai` | Gen AI tools (image, video, audio, 3D) with who pays for each, and what Auto offers. |
| `search skills\|tasks\|outputs "TERMS"` | Public Evals records. Use non-confidential terms only. |
| `upload FILE...` | Local files become input IDs (`--input`). The same file uploaded again returns the same ID. |
| `suggest --prompt-file F --count N [--input ID]` | The setups Evals' Battle planner picks for this brief. Save the JSON to a file and pass it to `prepare --suggestion FILE`. |
| `prepare --prompt-file F --private\|--public --setup SPEC ...` | Builds a plan for 2 to 8 setups and starts nothing. |
| `start PLAN_ID --confirm-spend` | Starts the approved plan and returns the run ID and a `review_url` for progress and recovery. |
| `status RUN_ID`, `wait RUN_ID --timeout S [--open]` | Each setup's latest state and its available `outputs_url`. With `--open`, wait opens an output after the setups settle. |
| `results RUN_ID --out DIR` | Downloads every setup's latest result. The manifest records each available browser link, including links to the signed-in viewer. File downloads expire after about 15 minutes. |
| `continue RUN_ID --setup N --prompt-file F` | Shows a follow-up turn for one setup; add `--confirm-spend` after the user approves it. |
| `retry RUN_ID --setup N` | Shows which attempt a retry would replace; add `--confirm-spend` after the user approves it. Same as Retry on the run page: a new attempt on the same model and payer. |
| `sessions --days N --out DIR` | Local only: lists the user's Claude Code and Codex sessions for `ultra-audit`, every user-role message kept with its source label. Uploads nothing. |
| `tally DIR --key key.json --weights weights.json` | Arithmetic only: adds up judges' `verdict.json` files for `ultra-judge`. |

A `--setup` is one option: `model=ID`, plus `gen=none|auto|EXACT_GEN_AI_NAME`, `skill=auto|none|SKILL_ID` (repeat `skill=` for several skills), `effort=LEVEL` and `runtime=native`. Leaving out `gen=` keeps Gen AI off. One `--setup` is a direct run; two to eight compare them.

`runtime=native` runs a ChatGPT-connected model in OpenAI's own Codex agent, which has live web search, instead of Evals' agent loop. Use it only where `models` shows `native_codex: true`; it is switched off on some servers. Claude models on a connected Claude account already run in Claude's own agent.

## Rules

1. **The brief is the user's.** Send it word for word. Keep instructions meant for the setups, including deliverable requirements. Never give one setup a hint the others do not get, and never rewrite the brief to make it "better". Write a brief from the conversation to a file and pass `--prompt-file`. A command file may add one shared footer (for example the research footer); show it in the review.
2. **Width means different families.** The point of an ultra run is setups from different labs (Anthropic, OpenAI, Google, xAI, DeepSeek, Moonshot, Alibaba and others), not one model eight times. Default is 8 setups; `--quick` means 4; a number the user gives wins (2 to 8).
3. **One review, then start.** Show the user, in one message: the brief, each setup with its model, Gen AI tool, skills, effort and payer, the inputs, the visibility, and the cost note. Start only after the user approves that exact plan. If the user already said, for this run, something like "go ahead, public is fine", that is the approval. Any change means a new `prepare` and a new review.
4. **Visibility.** `--private` or `--public` in the user's request decides it. Otherwise use `--private` when `whoami` allows it. Private needs an Evals Plus or Pro plan: if the user asked for private without one, say so with https://evals.ag/pricing and ask whether to run it public instead; never switch to public on your own. If only Public is available, say plainly that the brief, inputs and results will be public on Evals, and let the user decide. Briefs and files from the user's own sessions are private material: never make one public without an explicit yes.
5. **Who pays.** Setups on a connected Claude or ChatGPT (Codex) account, and Gen AI on a connected Higgsfield account, carry no Evals fee; they use that subscription's own limits. Every other model or tool is paid from the Evals balance at measured cost. Say which is which. If the user wants it free, use only what their connected accounts cover and say how many families that leaves. Total cost is unknown until the run records it. Never call a paid setup free.
6. **Report what happened.** Lead with the Output link when available. Private output links open in the signed-in viewer. Provide downloaded results when there is no browser link. Use Run Studio when the user needs progress, voting or recovery. Report each setup's actual state. If a start is refused or uncertain, check its status before trying again. A setup whose `results` entry says `produced_nothing: true` finished without a final answer or files. Report it as incomplete and offer `retry`. Files marked `input: true` are copies of the run's inputs. Runtime, tokens and charges are unknown until recorded. Attribute each finding to the setup or judge that produced it.
7. **Nothing is cut.** Read results in full. If they are too long for one pass, split them and read every part, or hand parts to sub-agents and merge every reply. If something was not read, say so.
8. **Judgments come from models, not scripts.** What a session was about, which result is better, what a report says: that is work for you or a sub-agent. Scripts only list, download and count.
