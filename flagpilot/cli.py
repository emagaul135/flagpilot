"""FlagPilot CLI (spec §2, §5).

Subcommands (``status`` is stretch — skipped in the scaffold):

- ``run "<prompt>"`` — parse → print plan → approval gate → (dry-run or
  live) steps in order. Nothing is written before approval, and every
  write step asks again.
- ``traffic`` — simulate shoppers (``--users 300``, seeded).
- ``results`` — refresh + print the experiment results in plain English.

Run with ``python -m flagpilot.cli`` from the repo root, or install the
package and use the ``flagpilot`` entry point (see README.md).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from . import __version__
from .client import FlagsmithClient, FlagsmithError
from .parse import CANONICAL_SPEC, parse_prompt
from .plan import ApprovalRefused, ask_approval, render_plan, require_approval
from .results import dashboard_link, print_results, refresh_and_fetch
from .traffic import DEFAULT_SEED, DEFAULT_USERS, run_live, simulate_users

REPO_ROOT = Path(__file__).resolve().parent.parent
DEMO_DIR = REPO_ROOT / "demo"
CONFIG_NAME = "flagpilot-config.json"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def load_binding(config_path: str | None = None) -> dict:
    """Read the project + environment binding written by
    ``flagsmith init`` (``flagsmith.json``). Safe to commit; contains no
    credentials. Returns {} when the file does not exist yet."""
    path = Path(config_path) if config_path else REPO_ROOT / "flagsmith.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return {}


def build_demo_config(
    spec, env_key: str | None
) -> dict:
    """The config the demo page reads — the wiring always matches the
    experiment the agent just created (spec §2, step 6)."""
    return {
        "flag": spec.flag,
        "environment_key": env_key or "",
        "metric_event": spec.metric_event,
        "variants": [
            {"key": var.key, "value": var.value} for var in spec.variations
        ],
    }


def write_demo_config(config: dict, demo_dir: Path | None = None) -> Path:
    path = (demo_dir or DEMO_DIR) / CONFIG_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, indent=2) + "\n")
    return path


def _extract_id(output: str, *keys: str) -> int | None:
    """Best-effort ID extraction from a JSON CLI response. Returns None
    when the ID cannot be found — the run then stops instead of guessing."""
    try:
        data = json.loads(output)
    except (json.JSONDecodeError, TypeError):
        return None
    if isinstance(data, dict):
        for key in keys:
            value = data.get(key)
            if isinstance(value, int):
                return value
    return None


def _extract_variation_ids(output: str) -> list[int] | None:
    """Pull the multivariate-option ids from a ``feature get --json``
    response (``multivariate_options`` list). Returns None when the
    shape is not as expected — the run then stops instead of guessing."""
    try:
        data = json.loads(output)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    options = data.get("multivariate_options") or data.get("options")
    if not isinstance(options, list) or not options:
        return None
    ids = [opt.get("id") for opt in options
           if isinstance(opt, dict) and isinstance(opt.get("id"), int)]
    return ids or None


# ---------------------------------------------------------------------------
# `run`
# ---------------------------------------------------------------------------


def cmd_run(args: argparse.Namespace) -> int:
    client = FlagsmithClient(
        dry_run=args.dry_run,
        env_key=args.env_key,
    )
    binding = load_binding(args.config)
    env_key = args.env_key or client.env_key or binding.get("environment_key")

    # Step 1 — parse (template parser, or the 3 questions).
    spec = parse_prompt(args.prompt)
    print(render_plan(spec))

    # Approval #1 — the plan. Anything but `y` stops with zero writes.
    try:
        require_approval("Approve this plan? [y/n] ")
    except ApprovalRefused:
        return 0

    if not args.dry_run and not client.api_key:
        print(
            "No FLAGSMITH_API_KEY set. Run with --dry-run to see the "
            "exact commands, or set the key (see .env.example)."
        )
        return 1

    # Step 0 — connect (read-only). In dry-run this only prints the checks.
    print("Checking the Flagsmith CLI…")
    try:
        version = client.check_version()
        if version and not args.dry_run:
            print(f"  CLI: {version}")
        client.auth_status()
        if env_key:
            client.warehouse_connections(env_key)
    except FlagsmithError as exc:
        print(f"Connection check failed: {exc}")
        print(
            "If there is no warehouse connection, enable the managed "
            "warehouse first: "
            "https://docs.flagsmith.com/experimentation/connect-a-warehouse"
        )
        return 1

    # Step 3 — create the multivariate flag (approval #2).
    try:
        require_approval(
            f"Create flag '{spec.flag}' with {len(spec.variations)} "
            "variants? [y/n] "
        )
        flag_json = client.create_flag(spec)
    except ApprovalRefused:
        return 0
    except FlagsmithError as exc:
        print(f"Flag creation failed: {exc}")
        return 1

    # Step 4 + 5 — metric + experiment (same approval gate).
    # Live mode needs the IDs from the responses; dry-run prints the
    # commands with placeholder IDs.
    flag_id = _extract_id(flag_json, "id") if not args.dry_run else 0
    if not args.dry_run and flag_id is None:
        print("Could not read the flag id from `feature get --json`. "
              "Stopping — no metric or experiment was created.")
        return 1
    try:
        require_approval(
            f"Create metric '{spec.metric_name}' and the experiment "
            f"'{spec.experiment_name}'? [y/n] "
        )
        metric_json = client.create_metric(
            spec.metric_name, spec.metric_event, env_key
        )
    except ApprovalRefused:
        return 0
    except FlagsmithError as exc:
        print(f"Metric creation failed: {exc}")
        return 1

    metric_id = _extract_id(metric_json, "id") if not args.dry_run else 0
    if not args.dry_run and metric_id is None:
        print("Could not read the metric id. Stopping — no experiment "
              "was created.")
        return 1
    # Variation ids come from the flag JSON in live mode; placeholders
    # in dry-run. The payload shape is exact (§2 step 5) either way.
    if args.dry_run:
        variation_ids = [0] * len(spec.variations)
    else:
        variation_ids = _extract_variation_ids(flag_json)
        if variation_ids is None or len(variation_ids) != len(spec.variations):
            print("Could not read the variation ids from "
                  "`feature get --json`. Stopping — no experiment was "
                  "created.")
            return 1
    try:
        exp_json = client.create_experiment(
            spec, flag_id or 0, metric_id or 0, variation_ids, env_key
        )
    except FlagsmithError as exc:
        print(f"Experiment creation failed: {exc}")
        return 1

    experiment_id = _extract_id(exp_json, "id") if not args.dry_run else 0
    if not args.dry_run and experiment_id is None:
        print("Could not read the experiment id. Stopping — the "
              "experiment was created but not started.")
        return 1

    # Step 6 — wire the demo shop (approval #4).
    config = build_demo_config(spec, env_key)
    print("Demo config to write (demo/flagpilot-config.json):")
    print(json.dumps(config, indent=2))
    try:
        require_approval("Write the demo config? [y/n] ")
    except ApprovalRefused:
        return 0
    if args.dry_run:
        print(f"[dry-run] would write {DEMO_DIR / CONFIG_NAME}")
    else:
        path = write_demo_config(config)
        print(f"Wrote {path}")

    # Step 7 — start the experiment (approval #5). Starting locks the
    # flag and turns on the rollout, so this is the last gate.
    try:
        require_approval("Start the experiment? [y/n] ")
        client.start_experiment(experiment_id, env_key)
    except ApprovalRefused:
        return 0
    except FlagsmithError as exc:
        print(f"Starting the experiment failed: {exc}")
        return 1

    print("")
    print("Experiment is running. Next:")
    print(f"  flagpilot traffic --users {DEFAULT_USERS}")
    print("  # wait about a minute, then:")
    print("  flagpilot results --experiment-id <id>")
    return 0


# ---------------------------------------------------------------------------
# `traffic`
# ---------------------------------------------------------------------------


def cmd_traffic(args: argparse.Namespace) -> int:
    if args.dry_run or not args.env_key:
        # Pure deterministic simulation — no SDK, no network.
        _, summary = simulate_users(users=args.users, seed=args.seed)
        print(summary.plain_english())
        if not args.env_key:
            print("")
            print("Dry-run simulation only (no --env-key). Pass --env-key "
                  "to send real events with the Python SDK.")
        return 0
    try:
        summary = run_live(
            users=args.users, seed=args.seed, environment_key=args.env_key
        )
    except (ImportError, ValueError) as exc:
        print(str(exc))
        return 1
    print(summary.plain_english())
    return 0


# ---------------------------------------------------------------------------
# `results`
# ---------------------------------------------------------------------------


def cmd_results(args: argparse.Namespace) -> int:
    client = FlagsmithClient(dry_run=args.dry_run, env_key=args.env_key)
    if args.dry_run:
        print("[dry-run] would call:")
        print("  POST .../experiments/<id>/results/refresh/")
        print("  GET  .../experiments/<id>/results/")
        if args.project_id and args.env_key:
            print("Dashboard: " + dashboard_link(
                args.project_id, args.env_key, args.experiment_id))
        return 0
    if not client.api_key:
        print("No FLAGSMITH_API_KEY set. Use --dry-run to preview.")
        return 1
    try:
        results = refresh_and_fetch(client, args.experiment_id, args.env_key)
    except FlagsmithError as exc:
        print(f"Results refresh failed: {exc}")
        return 1
    print_results(
        results,
        project_id=args.project_id or "",
        env_key=args.env_key or "",
        experiment_id=args.experiment_id,
    )
    return 0


# ---------------------------------------------------------------------------
# argparse
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="flagpilot",
        description=(
            "Turn a plain-English experiment idea into a live Flagsmith "
            "experiment. Every write asks for approval first."
        ),
    )
    parser.add_argument("--version", action="version",
                        version=f"flagpilot {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser(
        "run", help="Parse a prompt and run the experiment loop.")
    p_run.add_argument("prompt", help=(
        "The experiment idea, e.g. \"Test the checkout button copy: "
        "'Buy now' vs 'Get yours today'. Success is a purchase.\""))
    p_run.add_argument("--dry-run", action="store_true",
                       help="Print the exact commands; write nothing.")
    p_run.add_argument("--env-key", default=None,
                       help="Flagsmith environment key.")
    p_run.add_argument("--config", default=None,
                       help="Path to flagsmith.json (default: repo root).")
    p_run.set_defaults(func=cmd_run)

    p_traffic = sub.add_parser(
        "traffic", help="Simulate shoppers against the live experiment.")
    p_traffic.add_argument("--users", type=int, default=DEFAULT_USERS)
    p_traffic.add_argument("--seed", type=int, default=DEFAULT_SEED)
    p_traffic.add_argument("--env-key", default=None,
                           help="Send real events (live mode).")
    p_traffic.add_argument("--dry-run", action="store_true",
                           help="Deterministic simulation only.")
    p_traffic.set_defaults(func=cmd_traffic)

    p_results = sub.add_parser(
        "results", help="Refresh + print the experiment results.")
    p_results.add_argument("--experiment-id", type=int, required=True)
    p_results.add_argument("--project-id", default=None)
    p_results.add_argument("--env-key", default=None)
    p_results.add_argument("--dry-run", action="store_true")
    p_results.set_defaults(func=cmd_results)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except ApprovalRefused:
        return 0
    except FlagsmithError as exc:
        print(f"Error: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
