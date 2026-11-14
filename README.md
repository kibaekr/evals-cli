# Evals CLI

**Give the same brief to different AI setups and see what each actually makes.**

Try two models on a landing-page brief, see whether a skill improves an agent's work, or explore several creative directions before committing to one. Evals runs the setups in your account and gives you one Evals.ag link to inspect the outputs, compare recorded evidence, and continue from the result you want to keep.

[See the Odyssey brief and its public outputs](https://evals.ag/tasks/tsk_5MJR8GDMAJ7GA6MZY2NWWHVBQ8)

## Install with Claude Code or Codex

Paste this into your agent:

> Install the Evals skill from https://github.com/kibaekr/evals-cli for this agent. From the checkout, verify it with `python3 skills/evals/scripts/evals.py search outputs "The Odyssey" --limit 3`.

The repository is currently private. GitHub access is required to clone it. The bundled CLI needs Python 3.10 or newer and uses the standard library.

### Install the Skill Manually

```sh
git clone https://github.com/kibaekr/evals-cli.git
cd evals-cli

# Claude Code
mkdir -p ~/.claude/skills
cp -R skills/evals ~/.claude/skills/

# Codex
mkdir -p ~/.agents/skills
cp -R skills/evals ~/.agents/skills/
```

In a new session, use `/evals` in Claude Code or `$evals` in Codex. The skill can use its bundled Python script.

You can also install the Claude Code plugin from this repository:

```text
/plugin marketplace add kibaekr/evals-cli
/plugin install evals@evals
```

Use `/evals:evals` with the plugin install.

## Try It

In Claude Code, start with `/evals`. In Codex, start with `$evals`. For example:

```text
/evals Compare this branding brief with my design skill and with no skill. Use the same model both times.
```

| What you want to learn | What to ask |
| --- | --- |
| Which model fits this task? | Give two models the landing-page brief above. Keep the inputs and skills the same. I want to compare how clearly each explains the offer. |
| Does my skill help? | Compare my design skill against no skill on this branding brief. Use the same model and inputs for both. |
| Which direction should I develop? | Give this launch brief to three setups you recommend. I want three distinct directions I can review on Evals. |
| What has already worked on a similar task? | Find public Evals outputs for The Odyssey and link the original results and their recorded runtimes. |

For a new comparison, the agent keeps your brief intact, proposes setup choices you delegated, and shows the brief, inputs, visibility, and payer for review. Once you approve the plan, it starts the comparison and returns the run link. Open it to review the outputs and continue a branch. Public search works before you sign in.

## Use the Terminal

From the repository root on macOS or Linux:

```sh
mkdir -p ~/.local/bin
install -m 755 skills/evals/scripts/evals.py ~/.local/bin/evals
export PATH="$HOME/.local/bin:$PATH"

evals search outputs "The Odyssey" --limit 3
evals login
evals whoami
evals models
```

`evals login` opens the Evals device page. Sign in, match the code shown in your terminal, and approve the device. On a remote machine, use `evals login --no-browser` and open the printed URL in your browser. Disconnect with `evals logout` or from [CLI Devices](https://evals.ag/settings/cli).

Save your brief as `brief.txt`. Replace the model IDs below with IDs from `evals models`. Use `--visibility private` if your account is eligible and you want a private run.

```sh
evals compare --prepare-only --visibility public \
  --model MODEL_A --model MODEL_B --skill none --skill none \
  --prompt-file brief.txt
```

After you review the returned plan and authorize its visibility and charges:

```sh
evals start PLAN_ID --confirm-spend
evals status RUN_ID
```

To test a skill, find its ID with `evals search skills "design"`. Use the same model ID twice with `--skill none --skill SKILL_ID`. For scripts, `evals wait RUN_ID --timeout 120` reports settled attempts or times out with the latest state.

A public run can expose the brief, inputs, and outputs. The terminal comparison uses Gen AI off and supports input IDs from files already uploaded to your account. Total cost is determined during execution. The review shows which accounts or balance can pay.

## Use Evals in ChatGPT

The Evals MCP connection lets ChatGPT look up public work and read recorded evidence. In a workspace that supports custom MCP servers, go to **Plugins → Add → Add Custom MCP Server**. Name it **Evals**, enter `https://evals.ag/api/agent/mcp`, and choose **No Authentication**. Connect it and try this in a Work chat:

> @Evals Find public outputs for The Odyssey and link the original results.

Open a result on Evals.ag to inspect it. On the public task page, **Try this** opens the original brief in the composer so you can choose your own setup. You can also compare a new brief from your terminal agent.

[CLI Guide](https://evals.ag/agent-comparison) · [Evals.ag](https://evals.ag)
