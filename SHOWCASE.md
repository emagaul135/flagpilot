# FlagPilot — showcase scenarios (beyond the checkout demo)

Three extra plain-English prompts that show the agent's range. Each one
exercises a different FlagPilot muscle. Use them in the demo video after
the checkout example, or as the live-judging walkthrough. All three must
produce a human-approved plan before any write, like the main demo.

## 1. The careful rollout — "ramp it slowly"

Prompt:

```bash
flagpilot run "Roll out the new search ranking to 10% of users in Indonesia first. If it works, we will ramp it up. Track search clicks as success."
```

Why it shows range: a percentage rollout + a geo segment + a non-purchase
metric. Expected plan: flag `search_ranking_v2`, single variant vs control,
segment `country == ID`, rollout 10%, metric `search_click`.

## 2. The kill switch — "turn it off fast"

Prompt:

```bash
flagpilot run "We need a kill switch for the new recommendation widget. One flag, off by default, so we can disable it instantly without deploying."
```

Why it shows range: a boolean flag with no experiment at all — FlagPilot
is not only for A/B tests. Expected plan: flag `recommendations_widget`,
boolean, default off, no metric, no experiment. The demo beat: flip it on
in the dashboard, the widget appears on the demo page; flip it off, it
vanishes — in seconds, no deploy.

## 3. The pricing test — "which price wins"

Prompt:

```bash
flagpilot run "Test three prices for the Pro plan: $9, $12 and $15 a month. Success is a completed subscription. Split traffic evenly."
```

Why it shows range: three variants (not two), a revenue metric, and the
results table has to rank three arms. Expected plan: flag `pro_price`,
variants `price_9` / `price_12` / `price_15`, metric `subscription`,
33/33/34 split. The demo beat: the results printout names the leading
price with its win probability.

## Judging-day checklist

- [ ] All three prompts produce a correct plan on the first try (no rewording)
- [ ] Kill-switch flip is visible on the demo page in under 5 seconds
- [ ] Pricing results table ranks all three arms with exposures + conversions
- [ ] Every write step still asks for approval — say so out loud in the video
