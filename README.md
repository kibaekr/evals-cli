# Evals

**One task, eight AI model families, one link with every result.**

Arena-style skills make many copies of one model argue. Evals gives your real task to up to eight *different* model families at once (Claude, GPT, Gemini, Grok, DeepSeek and more), each on its own computer with real tools, and brings every result back to one Evals.ag page you can compare and keep working from.

[See the Odyssey brief and its public outputs](https://evals.ag/tasks/tsk_5MJR8GDMAJ7GA6MZY2NWWHVBQ8)

## Commands

Type them in Claude Code (`/evals …`) or Codex (`$evals …`), or just say "use evals ultra research to …".

| Command | What you get | Try |
| --- | --- | --- |
| `/evals compare-models` | The same brief on several models. Name them, or let Evals propose a lineup for your brief from the newest models. Only the model changes. | `/evals compare-models Opus vs GPT-6.1 Sol vs Gemini on this landing-page brief` |
| `/evals test-skills` | Your skill against a no-skill control on the same model and brief, with repeated controls to show how much the model varies on its own. | `/evals test-skills my brand-voice skill on this launch email` |
| `/evals ultra-design` | Eight design or brand directions: logos, landing pages, app screens, ads, thumbnails, short video. | `/evals ultra-design rebrand my coffee shop: logo, palette, menu board` |
| `/evals ultra-deck` | Eight sales, marketing, pitch or strategy decks from your notes and files. | `/evals ultra-deck a 10-slide seed pitch from this memo` |
| `/evals ultra-research` | Eight agents research one question with web access; one merged report of what they agreed on, what only one found, where they disagree and what nobody answered. | `/evals ultra-research every company selling eval data to AI labs: pricing, customers, funding` |
| `/evals ultra-judge` | A council of eight models scores your candidates blind against one rubric, with the votes tallied and how much the judges agreed. | `/evals ultra-judge which of these five ad cuts holds a viewer past three seconds` |
| `/evals ultra-audit` | Reads your recent Claude Code and Codex sessions on your machine, reports what you use AI for, and proposes runs on your real briefs to find what is cheaper or better. | `/evals ultra-audit` |
| `/evals compare` | A controlled test of one Gen AI tool or effort level against another. | `/evals compare Kling vs Veo for this product clip` |
| `/evals direct` | One model on one brief, then keep working on it. | `/evals direct GPT-6.1 Sol: a landing page for my bakery` |

Each command also has a shortcut skill (`/evals-compare-models`, `/evals-test-skills`, `/evals-ultra-design`, …). Add `--quick` to an ultra command for four setups instead of eight, and `--private` (Evals Plus or Pro) or `--public` to choose who can see the run.

Every run is reviewed before it starts: the brief, each setup's model, Gen AI tool, skills, effort and who pays, the inputs and the visibility. Setups on your connected Claude or ChatGPT account, and images or video on your connected Higgsfield account, carry no Evals fee; other models and tools are paid from your Evals balance at measured cost. Total cost is known once the run records it.

## Install

Paste this into Claude Code or Codex:

> Install the Evals skills from https://github.com/kibaekr/evals-cli for this agent: copy every folder under `skills/` into my skills folder. Then run `python3 <skills folder>/evals/scripts/evals.py login` and show me the approval link.

The repository is currently private; GitHub access is required to clone it. The bundled CLI needs Python 3.10 or newer and only the standard library.

### Manually

```sh
git clone https://github.com/kibaekr/evals-cli.git && cd evals-cli
mkdir -p ~/.claude/skills ~/.agents/skills
cp -R skills/* ~/.claude/skills/    # Claude Code
cp -R skills/* ~/.agents/skills/    # Codex
python3 skills/evals/scripts/evals.py login
```

Copy all the folders: the `evals-ultra-*` shortcuts read the `evals` folder next to them. `login` prints an evals.ag link and a device code: sign in there, or create a free account, and approve the device. On a remote machine add `--no-browser`. Disconnect with `logout` or from [CLI Devices](https://evals.ag/settings/cli).

As a Claude Code plugin:

```text
/plugin marketplace add kibaekr/evals-cli
/plugin install evals@evals
```

Plugin skills are namespaced (`/evals:evals ultra-design`, `/evals:evals-ultra-design`), and plain requests such as "use evals ultra design" work the same.

## Use the terminal

```sh
install -m 755 skills/evals/scripts/evals.py ~/.local/bin/evals
evals --help
```

If another `evals` is already on your PATH (npm's `evals` package installs one), install it under another name such as `evals-ag`. The skills never depend on PATH; they run the bundled script.

```sh
evals whoami                      # account and Private eligibility
evals models [--gen-ai]           # LLMs, or Gen AI tools, with who pays
evals upload logo.png notes.pdf   # input IDs
evals suggest --prompt-file brief.md --count 8 > suggestion.json   # Evals' Battle lineup
evals prepare --private --prompt-file brief.md --suggestion suggestion.json
evals prepare --private --prompt-file brief.md \
  --setup "model=MODEL_A,gen=auto,effort=high" --setup "model=MODEL_B,gen=auto,runtime=native" ...
evals start PLAN_ID --confirm-spend
evals wait RUN_ID --timeout 600
evals results RUN_ID --out results/
evals continue RUN_ID --setup 2 --prompt-file next.md [--confirm-spend]
evals retry RUN_ID --setup 2 [--confirm-spend]       # the run page's Retry
evals sessions --days 7 --out audit/   # local only, uploads nothing
evals tally verdicts/ --key key.json --weights weights.json
```

`prepare` creates no run. `start` creates it, starts every setup and opens the run's blind comparison. `--public` runs show the brief, inputs and results to anyone; `--private` needs an Evals Plus or Pro plan.

## Use Evals in ChatGPT

The Evals MCP connection lets ChatGPT look up public work and read recorded evidence. In a workspace that supports custom MCP servers, go to **Plugins → Add → Add Custom MCP Server**. Name it **Evals**, enter `https://evals.ag/api/agent/mcp`, and choose **No Authentication**. Then try:

> @Evals Find public outputs for The Odyssey and link the original results.

[CLI Guide](https://evals.ag/agent-comparison) · [Evals.ag](https://evals.ag)
