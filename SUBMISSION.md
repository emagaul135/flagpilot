# FlagPilot — submission notes (honest build notes)

_Draft — finalised at submission time (Fri 27 Nov 2026)._

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

## What Muse built vs what the user did

- **Muse (this scaffold + Day 1–2 build):** the agent code, the demo shop,
  the tests, the docs, the dry-run verification.
- **User (human-only steps):** WeMakeDevs account + Toggle Wars
  registration; Flagsmith Cloud free account; the Master API key (passed
  via Secure Vault, never in chat or the repo); typing `y` at every
  approval gate in the demo video; the submission itself.
- **The demo video** shows the real CLI, the real dashboard and the real
  demo page — no mockups. The traffic is simulated (300 synthetic
  shoppers, `sim-001`…`sim-300`, seeded RNG) and the video says so.

## LLM vs template path

The agent has two parsing paths. The Gemini LLM path is optional and was
[stubbed / wired — update at submission]: without a Gemini key the
deterministic template parser runs the whole demo — it parses the
canonical phrasings ("Test X: A vs B. Success is Y.") and asks the three
clarifying questions from the official prompt when a prompt doesn't
parse, instead of guessing. The demo video uses the [template / LLM —
update] path.

## What was NOT faked

- The flag, metric and experiment are real objects on the free Flagsmith
  Cloud account; the results are the real warehouse numbers.
- The approval gates are real: refusing stops the run with zero writes
  (covered by `tests/test_plan.py`).
- No secrets in the repo: `.env` / `flagsmith.env` gitignored,
  `flagsmith.json` contains no credentials.

## Known limits (to verify on Day 1–2)

- [ ] Exact `flagsmith api` flags for method + body (scaffold uses
  `flagsmith api <path> --method POST --data '<json>'`)
- [ ] Exact Python SDK `track_event` method name/signature
- [ ] Exact JS SDK bundle path/version for the demo page CDN
- [ ] Exact results-payload shape for the plain-English printout
- [ ] Free-plan experimentation + managed-warehouse MTUE allowance on the
  live dashboard
- [ ] Exact WeMakeDevs submission form fields (read after registering)

## Track

**Track 02 — AI Agents and Feature Flags** ($1,000 cash, one winner).
