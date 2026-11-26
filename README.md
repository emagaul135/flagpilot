# FlagPilot

**Toggle Wars — Track 02: AI Agents and Feature Flags.** One prompt in, one live
Flagsmith experiment out.

Running a real A/B test by hand means clicking through the Flagsmith
dashboard — create the flag, add the variants, define the metric, wire the
experiment, instrument the code, then remember to check the results.
FlagPilot collapses all of that into one command: it parses your prompt,
shows you exactly what it is about to change, and only writes anything
after you say yes. Ten minutes later you have a running experiment with
live results.

**Demo video (2:00):** https://www.youtube.com/watch?v=9Dc3sPEo2h0
· **Live demo shop:** https://emagaul135.github.io/flagpilot/demo/
· **Live experiment:** flag `checkout_button`, "Get yours today" winning
at 88.2% chance to win (300 shoppers, 27 Nov 2026).

## What it does

```bash
flagpilot run "Test the checkout button copy: 'Buy now' vs 'Get yours today'. Success is a purchase."
```

1. **Parses** the prompt into an experiment spec — Gemini LLM if a key is
   set, otherwise a deterministic template parser (plus three clarifying
   questions if the prompt doesn't parse — it never guesses).
2. **Prints the plan** — flag, variants with keys, metric, experiment,
   rollout — and asks `Approve this plan? [y/n]`. Anything but `y` stops
   with zero writes. Every write step asks again.
3. **Creates** the multivariate flag (`checkout_button`: `Buy now` /
   `Get yours today`, 50/50) with the Flagsmith CLI v2, then the metric
   (`purchase`) and the experiment via `flagsmith api` — the exact payloads
   from the official "Set Up an Experiment with a Coding Agent" prompt.
4. **Wires** the demo shop by writing `demo/flagpilot-config.json`.
5. **Starts** the experiment, **simulates** 300 shoppers, and **prints**
   the results in plain English with the win probability and a dashboard link.

It uses the Flagsmith **CLI + REST API** — deliberately not the MCP server:
the official docs say the MCP server can't start experiments.

## Setup (a judge can follow this)

```bash
# 1. Install the Flagsmith CLI v2
curl -fsSL https://get.flagsmith.com | sh
flagsmith --version          # must report v2 or later

# 2. Install the agent
pip install -r requirements.txt
pip install -r requirements-dev.txt   # pytest, for the tests

# 3. Configure (keys live ONLY in .env — never in the repo)
cp .env.example .env
# edit .env: FLAGSMITH_API_KEY=<your Master API key>
#            GEMINI_API_KEY=<optional, Google AI Studio>
#            FLAGSMITH_ENVIRONMENT_KEY=<your environment key>

# 4. Bind the project + environment (writes flagsmith.json)
flagsmith init --project flagpilot

# 5. Enable the managed warehouse FIRST (Environment Settings → Warehouse),
#    then send a test event — first-event processing can take a while.
#    Without a warehouse connection the agent stops with the docs link.
```

## The demo in 5 commands

```bash
# 1. Dry run — see the exact plan and commands, zero writes
flagpilot run "Test the checkout button copy: 'Buy now' vs 'Get yours today'. Success is a purchase." --dry-run

# 2. Live run — approve each step as it asks
flagpilot run "Test the checkout button copy: 'Buy now' vs 'Get yours today'. Success is a purchase."

# 3. Serve the demo shop (open http://localhost:8000 in two browser profiles
#    to see both button variants)
cd demo && python3 -m http.server 8000

# 4. Simulate 300 shoppers
flagpilot traffic --users 300 --env-key $FLAGSMITH_ENVIRONMENT_KEY

# 5. Read the results (wait about a minute after traffic)
flagpilot results --experiment-id <id> --project-id <id> --env-key $FLAGSMITH_ENVIRONMENT_KEY
```

Run the tests (no network, no Flagsmith account needed):

```bash
pytest -q
```

## Demo scenario (fixed, spec §4)

- **Flag:** `checkout_button` — control `Buy now` (key `control`),
  variant `Get yours today` (key `get_yours`), 50/50, rollout 100%.
- **Metric:** `purchase` (event `purchase`, occurrence, up).
- **Experiment:** "Checkout button copy — Nov 2026" — hypothesis: the
  "Get yours today" button converts more shoppers than "Buy now".
- **Traffic:** 300 simulated shoppers (`sim-001`…`sim-300`, seeded):
  control converts ~5%, variant ~9%.

## Repo layout

```
flagpilot/            # the agent package
  cli.py              # argparse: run / traffic / results
  parse.py            # LLM stub + deterministic template parser + 3 questions
  plan.py             # plan rendering + approval gates
  client.py           # subprocess wrapper: `flagsmith` CLI + `flagsmith api`
  traffic.py          # 300-shopper simulator (Python SDK, flush on exit)
  results.py          # results refresh + plain-English printout + dashboard link
demo/                 # ShopDemo: one product, one checkout button
tests/                # pytest: parser + plan/approval (no network)
DEMO.md               # the timed demo-video script
SUBMISSION.md         # honest build notes
```

## Honest notes

- No secrets anywhere in this repo. `.env` and `flagsmith.env` are
  gitignored; `flagsmith.json` (project + environment binding) is safe to
  commit by design.
- The demo traffic uses synthetic identifiers (`sim-001`…`sim-300`) — no
  real user data anywhere.
- The LLM parsing path is stubbed: without a Gemini key the template
  parser runs the whole demo. See `SUBMISSION.md`.
- Demo video: _link added at submission time_.
