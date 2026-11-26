# FlagPilot — demo video script (<3 min, target ~2:30)

Narration in English. Screen recordings of the real CLI, the real
Flagsmith dashboard and the real demo page only — no mockups.

## 0:00–0:20 — the problem

Show the Flagsmith dashboard. "Setting up a real A/B test by hand is five
dashboard chores: create the flag, add the variants, define the metric,
wire the experiment, instrument the code. FlagPilot does it from one
prompt." Type the prompt in the terminal:

```bash
flagpilot run "Test the checkout button copy: 'Buy now' vs 'Get yours today'. Success is a purchase."
```

## 0:20–0:50 — parse + plan + approval

The agent prints the plan — flag `checkout_button`, variants `Buy now` /
`Get yours today` with keys `control` / `get_yours`, metric `purchase`,
experiment "Checkout button copy — Nov 2026", 50/50, rollout 100%.
The human types `y`. "Nothing was written before that yes — and every
write step asks again."

## 0:50–1:30 — the dashboard + the demo page

The flag, metric and experiment appear in the Flagsmith dashboard (real
screens). Switch to the demo page in two browser profiles / two
identifiers: one sees "Buy now", the other sees "Get yours today".
Click a button — a `purchase` event is tracked.

## 1:30–2:10 — traffic + results

```bash
flagpilot traffic --users 300
# wait about a minute
flagpilot results --experiment-id <id>
```

300 simulated shoppers run. Results refresh. The printout reads out
exposures, conversions and the win probability per variant, plus the
dashboard link. Show the real Flagsmith results page with the same numbers.

## 2:10–2:30 — end card

"FlagPilot — Track 02, AI Agents and Feature Flags. Repo link on screen.
Built with Muse + the Flagsmith CLI and REST API."

## Recording checklist

- [x] Warehouse connected before recording (first-event processing is slow)
- [x] Results confirmed live in the dashboard before pressing record
- [x] Two browser profiles ready for the two button variants — demo page
      accepts `?id=<identifier>`: `?id=probe-02` renders control ("Buy
      now"), `?id=probe-01` renders the variant ("Get yours today")
- [x] Terminal font large enough to read on video
- [x] Live numbers (27 Nov 2026 ~06:31 WIB): control 157 exp / 12 purch,
      variant 145 exp / 19 purch, lift +71%, chance to win 88.2%
