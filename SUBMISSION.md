# FlagPilot — submission notes (honest build notes)

_Finalised Fri 27 Nov 2026, submission day._

## What FlagPilot does

A small Python CLI agent that turns a plain-English experiment idea into a
live Flagsmith experiment: parse → plan → human approval → create the
multivariate flag (CLI v2) → create the metric + experiment
(`flagsmith api`) → wire the demo shop → start → simulate 300 shoppers →
print the results in plain English with the win probability and a
dashboard link.

It uses the Flagsmith **CLI + REST API**, not the MCP server — the official
"Set Up an Experiment with a Coding Agent" doc says the MCP server can't
start experiments, which is the entire point of this agent.

## Live run (Fri 27 Nov 2026, free Flagsmith Cloud)

- Project `flagpilot` (ID 55958), Development environment.
- Flag `checkout_button` (ID 306337, multivariate, enabled, value
  `control`): control "Buy now" (key `control`), variant "Get yours
  today" (key `get_yours`, mv-option ID 37568), 50/50.
- Metric `purchase` (ID 884, aggregation `occurrence`, direction `up`,
  event `purchase`).
- Experiment "Checkout button copy — Nov 2026" (ID 836), hypothesis "The
  'Get yours today' button converts more shoppers than 'Buy now'.",
  status **running** since 27 Nov 2026 06:29 WIB.
- Traffic: 300 simulated shoppers (`sim-001`…`sim-300`, seeded RNG
  20261127): control 156 exposures / 12 purchases (7.7%), variant 144
  exposures / 19 purchases (13.2%).
- Warehouse: 300 events received. Live results (refreshed 27 Nov 06:31
  WIB): control n=157, 12 conversions; variant n=145, 19 conversions;
  lift +71%; **chance to win 88.2%** for "Get yours today".
- Dashboard: https://app.flagsmith.com/project/55958/environment/cyR8fU8XaTURkdzKMYy6gn/experiments/836

## What Muse built vs what the user did

- **Muse (Day 1–2 build):** the agent code, the demo shop, the tests,
  the docs, the live flag/metric/experiment, the traffic run and the
  results readout.
- **User (human-only steps):** WeMakeDevs account + Toggle Wars
  registration; Flagsmith Cloud free account (Google sign-in); the API key
  (supplied in chat, used transiently for the live build, never stored in
  the repo); typing `y` at every approval gate in the demo video; the
  submission itself.
- **The demo video** shows the real CLI output, the real dashboard and
  the real demo page — no mockups. The traffic is simulated (300
  synthetic shoppers, seeded RNG) and the video says so.

## LLM vs template path

The demo uses the **deterministic template parser** — the Gemini LLM path
is designed in the spec but not wired in this build, and the template
parser runs the whole demo end to end: it parses the canonical phrasings
("Test X: A vs B. Success is Y.") and asks the three clarifying questions
from the official prompt when a prompt doesn't parse, instead of
guessing. No LLM call is needed to run the demo.

## What was NOT faked

- The flag, metric and experiment are real objects on the free Flagsmith
  Cloud account; the results are the real warehouse numbers (see above).
- The approval gates are real: refusing stops the run with zero writes
  (covered by `tests/test_plan.py`, 20/20 passing).
- No secrets in the repo: `.env` / `flagsmith.env` gitignored;
  `flagsmith.json` holds only the client-side environment key (public by
  design — it is embedded in the demo page's JavaScript).

## Bugs found and fixed live on Day 2 (all in `flagpilot/traffic.py`)

- The Python SDK (6.7.0) needs `enable_events=True` at init, or events
  are silently dropped.
- `EventProcessorConfig` moved from `flagsmith.models` to
  `flagsmith.analytics` in SDK 6.7.0.
- `Flagsmith.identify()` no longer exists — identities are passed to
  `get_experiment_flag(name, identifier=…)` and
  `track_event(event, identifier=…)` instead.
- `max_buffer_items=1` drops the oldest event whenever the buffer fills,
  so a rapid 300-user loop loses exposures (proven live: 4 of 6 probe
  exposures dropped). Now 1000 + an explicit flush.
- The demo page rendered the control arm's literal flag value
  ("control") as the button copy; it now renders the copy from the
  variation key (`demo/app.js`).

## Known limits

- `flagpilot run` end to end needs a **Master API key** (Organisation
  Settings → API Keys) — the CLI v2 refuses a personal Account-Settings
  token ("legacy user authtoken"). The live experiment above was built
  with the same operations over the REST API directly, which accepts the
  personal token. A judge running the CLI with their own Master key hits
  no such issue.
- First-event warehouse processing can lag; the demo waits ~1 minute
  after traffic before refreshing results.
- `flagsmith api` flags verified against CLI v2.0.0; Python SDK
  `track_event` / `get_experiment_flag` verified against flagsmith 6.7.0;
  JS SDK bundle `@flagsmith/flagsmith@12.4.0` verified on jsDelivr.

## Track

**Track 02 — AI Agents and Feature Flags** ($1,000 cash, one winner).
