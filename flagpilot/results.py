"""Results refresh + plain-English printout + dashboard link
(spec §2, step 8).

About a minute after traffic, the agent refreshes the results
(allowed once every 5 minutes) and reads them. The printout is the
"Clear output" judging criterion: per-variant exposures, conversions,
conversion rate and the win probability — plus the dashboard link.
"""

from __future__ import annotations

import json
from typing import Any

from .client import FlagsmithClient

DASHBOARD_BASE = "https://app.flagsmith.com"


def dashboard_link(project_id: str, env_key: str, experiment_id: int) -> str:
    """``<dashboard>/project/<project id>/environment/<env key>/experiments/<id>``."""
    return (
        f"{DASHBOARD_BASE}/project/{project_id}/environment/{env_key}"
        f"/experiments/{experiment_id}"
    )


def refresh_and_fetch(
    client: FlagsmithClient, experiment_id: int, env_key: str | None = None
) -> dict[str, Any]:
    """POST results/refresh, then GET results. Returns the parsed JSON."""
    client.refresh_results(experiment_id, env_key=env_key)
    raw = client.get_results(experiment_id, env_key=env_key)
    try:
        return json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        return {"raw": raw}


def _variant_rows(results: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalise the results payload into per-variant rows.

    The exact results payload shape is VERIFY AT BUILD against the live
    API; this accepts the documented shape (a ``results``/``variants``
    list with exposure/conversion counts) and falls back to echoing the
    raw payload.
    """
    for key in ("results", "variants", "experiment_results"):
        rows = results.get(key)
        if isinstance(rows, list) and rows:
            return rows
    return []


def print_results(
    results: dict[str, Any],
    project_id: str = "",
    env_key: str = "",
    experiment_id: int = 0,
    print_fn=print,
) -> None:
    """Print the result in plain English."""
    rows = _variant_rows(results)
    print_fn("Experiment results")
    print_fn("==================")
    if not rows:
        print_fn("No per-variant results yet — the warehouse may still be")
        print_fn("processing events. Wait a few minutes, then run")
        print_fn("`flagpilot results` again.")
        if results:
            print_fn(f"Raw payload: {json.dumps(results)[:500]}")
    for row in rows:
        name = row.get("name") or row.get("key") or row.get("variant") or "?"
        exposures = row.get("exposures", row.get("exposure_count", "?"))
        conversions = row.get("conversions", row.get("conversion_count", "?"))
        rate = row.get("conversion_rate", row.get("rate"))
        win = row.get("win_probability", row.get("probability"))
        line = f"  {name}: {exposures} exposures, {conversions} conversions"
        if isinstance(rate, (int, float)):
            line += f" ({rate:.1%})"
        if isinstance(win, (int, float)):
            line += f" — win probability {win:.1%}"
        print_fn(line)
    if project_id and env_key and experiment_id:
        print_fn("")
        print_fn("Dashboard: " + dashboard_link(project_id, env_key, experiment_id))
