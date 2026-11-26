"""Subprocess wrapper around the Flagsmith CLI v2 + ``flagsmith api``
(spec §2 steps 0, 3–5, 7–8; §3).

- Flag work goes through the CLI: ``feature create``, ``feature variant
  add``, ``feature get --json``.
- Metric, experiment, start and results go through the REST API via
  ``flagsmith api`` — the CLI has no dedicated experiment subcommands.
- The payloads are the EXACT payloads from spec §2 steps 4–5.
- Dry-run mode prints the exact commands without running them.
- The API key is never printed or logged (it is passed only as an
  environment variable to the subprocess).

VERIFY AT BUILD (Day 1, against the live CLI): the exact
``flagsmith api`` flags for method + body. The scaffold uses
``flagsmith api <path> --method POST --data '<json>'`` per the CLI v2
reference; if the live CLI wants a different spelling, only
:meth:`FlagsmithClient.api` changes.
"""

from __future__ import annotations

import json
import os
import subprocess
from typing import Any, Optional

from .parse import ExperimentSpec


class FlagsmithError(Exception):
    """A CLI/API step failed. The run stops with this error printed —
    never a silent skip, never a guessed workaround (spec §2)."""


class FlagsmithClient:
    """Thin wrapper around the ``flagsmith`` CLI.

    ``dry_run=True`` prints every command and records it in ``self.log``
    instead of running it — that is how the agent proves zero writes
    before approval, and how the tests assert on it.
    """

    def __init__(
        self,
        dry_run: bool = False,
        api_key: Optional[str] = None,
        env_key: Optional[str] = None,
        print_fn=print,
    ) -> None:
        self.dry_run = dry_run
        self.api_key = api_key or os.environ.get("FLAGSMITH_API_KEY")
        self.env_key = env_key or os.environ.get("FLAGSMITH_ENVIRONMENT_KEY")
        self.print_fn = print_fn
        self.log: list[str] = []  # every command, dry-run or live

    # -- plumbing ---------------------------------------------------------

    def _env(self) -> dict[str, str]:
        env = dict(os.environ)
        if self.api_key:
            env["FLAGSMITH_API_KEY"] = self.api_key
        return env

    def _run(self, argv: list[str]) -> str:
        """Run one CLI command (or print + record it in dry-run mode)."""
        cmd = " ".join(argv)
        self.log.append(cmd)
        if self.dry_run:
            self.print_fn(f"[dry-run] $ {cmd}")
            return ""
        result = subprocess.run(
            argv, capture_output=True, text=True, env=self._env()
        )
        if result.returncode != 0:
            raise FlagsmithError(
                f"Command failed ({result.returncode}): {cmd}\n"
                f"{result.stderr.strip()}"
            )
        return result.stdout

    # -- step 0: connect (read-only) --------------------------------------

    def check_version(self) -> str:
        """``flagsmith --version`` must report v2 or later."""
        return self._run(["flagsmith", "--version"]).strip()

    def auth_status(self) -> str:
        """``flagsmith auth status`` must be green."""
        return self._run(["flagsmith", "auth", "status"]).strip()

    def warehouse_connections(self, env_key: Optional[str] = None) -> str:
        """``GET api/v1/environments/<env key>/warehouse-connections/``.

        Must return a connection. If none, the agent stops with the docs
        link — it does not guess or work around it (official prompt,
        step 3).
        """
        key = env_key or self.env_key
        if not key:
            raise FlagsmithError(
                "No environment key. Run `flagsmith init` first, or set "
                "FLAGSMITH_ENVIRONMENT_KEY."
            )
        return self.api(f"api/v1/environments/{key}/warehouse-connections/",
                        method="GET")

    # -- step 3: multivariate flag ----------------------------------------

    def feature_create(self, flag: str) -> str:
        return self._run(
            ["flagsmith", "feature", "create", flag,
             "--value", "control", "--enabled"]
        )

    def feature_variant_add(
        self, flag: str, value: str, key: str, weight: int = 0
    ) -> str:
        return self._run(
            ["flagsmith", "feature", "variant", "add", flag,
             "--value", value, "--key", key, "--weight", str(weight)]
        )

    def feature_get(self, flag: str) -> str:
        return self._run(["flagsmith", "feature", "get", flag, "--json"])

    def create_flag(self, spec: ExperimentSpec) -> str:
        """Create the multivariate flag + one call per variation, then
        verify with ``feature get --json``. Reuse is a Day-1 live concern
        (lookup first, never duplicate) — the scaffold always creates."""
        self.feature_create(spec.flag)
        for var in spec.variations:
            self.feature_variant_add(spec.flag, var.value, var.key)
        return self.feature_get(spec.flag)

    # -- generic REST via `flagsmith api` ---------------------------------

    def api(
        self,
        path: str,
        method: str = "GET",
        payload: Optional[dict[str, Any]] = None,
    ) -> str:
        argv = ["flagsmith", "api", path, "--method", method]
        if payload is not None:
            argv += ["--data", json.dumps(payload)]
        return self._run(argv)

    # -- step 4: metric (exact §2 payload) --------------------------------

    def metric_payload(self, name: str, event: str) -> dict[str, Any]:
        return {
            "name": name,
            "aggregation": "occurrence",
            "direction": "up",
            "definition": {"version": 1, "event": event},
        }

    def create_metric(
        self, name: str, event: str, env_key: Optional[str] = None
    ) -> str:
        key = env_key or self.env_key
        if not key:
            raise FlagsmithError("No environment key (see warehouse_connections).")
        return self.api(
            f"api/v1/environments/{key}/experiment-metrics/",
            method="POST",
            payload=self.metric_payload(name, event),
        )

    # -- step 5: experiment (exact §2 payload) ----------------------------

    def experiment_payload(
        self,
        spec: ExperimentSpec,
        flag_id: int,
        metric_id: int,
        variation_ids: list[int],
    ) -> dict[str, Any]:
        """Build the exact §2 step-5 payload. Each variation gets its
        ``percentage_allocation``; control gets the rest (the flag's own
        value is the ``feature_state_value``)."""
        allocations = []
        control_share = 100
        for i, var_id in enumerate(variation_ids):
            pct = spec.split_percentages[i] if i < len(spec.split_percentages) else 0
            allocations.append(
                {"multivariate_feature_option": var_id,
                 "percentage_allocation": pct}
            )
            control_share -= pct
        return {
            "feature": flag_id,
            "name": spec.experiment_name,
            "hypothesis": spec.hypothesis,
            "metrics": [{"metric": metric_id,
                         "expected_direction": "increase"}],
            "experiment_rollout": {
                "enabled": True,
                "rollout_percentage": spec.rollout_percentage,
                "feature_state_value": {"type": "string", "value": "control"},
                "multivariate_feature_state_values": allocations,
            },
        }

    def create_experiment(
        self,
        spec: ExperimentSpec,
        flag_id: int,
        metric_id: int,
        variation_ids: list[int],
        env_key: Optional[str] = None,
    ) -> str:
        key = env_key or self.env_key
        if not key:
            raise FlagsmithError("No environment key (see warehouse_connections).")
        return self.api(
            f"api/v1/environments/{key}/experiments/",
            method="POST",
            payload=self.experiment_payload(spec, flag_id, metric_id,
                                            variation_ids),
        )

    # -- step 7: start ------------------------------------------------------

    def start_experiment(
        self, experiment_id: int, env_key: Optional[str] = None
    ) -> str:
        key = env_key or self.env_key
        if not key:
            raise FlagsmithError("No environment key (see warehouse_connections).")
        return self.api(
            f"api/v1/environments/{key}/experiments/{experiment_id}/start/",
            method="POST",
        )

    # -- step 8: results ----------------------------------------------------

    def refresh_results(
        self, experiment_id: int, env_key: Optional[str] = None
    ) -> str:
        """Allowed once every 5 minutes."""
        key = env_key or self.env_key
        if not key:
            raise FlagsmithError("No environment key (see warehouse_connections).")
        return self.api(
            f"api/v1/environments/{key}/experiments/{experiment_id}/results/refresh/",
            method="POST",
        )

    def get_results(
        self, experiment_id: int, env_key: Optional[str] = None
    ) -> str:
        key = env_key or self.env_key
        if not key:
            raise FlagsmithError("No environment key (see warehouse_connections).")
        return self.api(
            f"api/v1/environments/{key}/experiments/{experiment_id}/results/",
            method="GET",
        )
