"""The 300-shopper traffic simulator (spec §2, step 8; §4).

For each simulated shopper (own identifier ``sim-001`` … ``sim-300``),
the Python SDK (``flagsmith`` 6.3.0+) initialises with events enabled,
calls ``get_experiment_flag('checkout_button')`` and tracks the
``purchase`` event for a seeded share of them — control converts at ~5%,
variant at ~9%, so the demo is repeatable and the variant visibly wins.
Events are flushed before exit (large buffer + explicit flush — a
``max_buffer_items=1`` buffer drops the oldest event when it fills, so it
must not be used for a rapid 300-user loop).

Offline-safe: :func:`simulate_users` is pure and deterministic (seeded
RNG, no network, no SDK needed) — that is what the tests exercise and
what ``flagpilot traffic --dry-run`` prints. The live SDK path
(:func:`run_live`) imports ``flagsmith`` lazily and is only used when a
real environment key is present.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

FLAG_NAME = "checkout_button"
METRIC_EVENT = "purchase"
DEFAULT_USERS = 300
DEFAULT_SEED = 20261127  # fixed in the repo so the demo is repeatable

# Seeded conversion rates (spec §4).
CONTROL_RATE = 0.05
VARIANT_RATE = 0.09


@dataclass
class ShopperResult:
    identifier: str
    variant_key: str  # "control" or "get_yours"
    converted: bool


@dataclass
class SimulationSummary:
    users: int
    seed: int
    control_exposures: int
    control_conversions: int
    variant_exposures: int
    variant_conversions: int

    @property
    def control_rate(self) -> float:
        return self.control_conversions / max(self.control_exposures, 1)

    @property
    def variant_rate(self) -> float:
        return self.variant_conversions / max(self.variant_exposures, 1)

    def plain_english(self) -> str:
        return (
            f"{self.users} simulated shoppers (seed {self.seed}):\n"
            f"  control ('Buy now'):        "
            f"{self.control_exposures} exposures, "
            f"{self.control_conversions} purchases "
            f"({self.control_rate:.1%})\n"
            f"  variant ('Get yours today'): "
            f"{self.variant_exposures} exposures, "
            f"{self.variant_conversions} purchases "
            f"({self.variant_rate:.1%})"
        )


def simulate_users(
    users: int = DEFAULT_USERS, seed: int = DEFAULT_SEED
) -> tuple[list[ShopperResult], SimulationSummary]:
    """Deterministic simulation. 50/50 assignment, seeded conversion."""
    rng = random.Random(seed)
    results: list[ShopperResult] = []
    control_exp = control_conv = variant_exp = variant_conv = 0
    for n in range(1, users + 1):
        identifier = f"sim-{n:03d}"
        variant = "control" if rng.random() < 0.5 else "get_yours"
        rate = CONTROL_RATE if variant == "control" else VARIANT_RATE
        converted = rng.random() < rate
        results.append(ShopperResult(identifier, variant, converted))
        if variant == "control":
            control_exp += 1
            control_conv += int(converted)
        else:
            variant_exp += 1
            variant_conv += int(converted)
    summary = SimulationSummary(
        users=users,
        seed=seed,
        control_exposures=control_exp,
        control_conversions=control_conv,
        variant_exposures=variant_exp,
        variant_conversions=variant_conv,
    )
    return results, summary


def run_live(
    users: int = DEFAULT_USERS,
    seed: int = DEFAULT_SEED,
    environment_key: str = "",
    print_fn=print,
) -> SimulationSummary:
    """Run the simulation against the real Flagsmith Cloud environment.

    Each shopper is a real identity: the SDK initialises with events
    enabled, ``get_experiment_flag`` serves the variant, and a seeded
    share track the ``purchase`` event. Events flush before exit.

    VERIFY AT BUILD (Day 2): the exact Python SDK method names against
    the Python tab of the "Run an Experiment" doc — ``get_experiment_flag``
    is confirmed; the ``track_event`` name/signature is the one to check.
    """
    if not environment_key:
        raise ValueError(
            "No environment key. Set FLAGSMITH_ENVIRONMENT_KEY or pass "
            "--env-key."
        )
    try:
        from flagsmith import Flagsmith  # type: ignore
        from flagsmith.analytics import EventProcessorConfig  # type: ignore
    except ImportError as exc:
        raise ImportError(
            "The `flagsmith` Python SDK is not installed. "
            "Run: pip install -r requirements.txt"
        ) from exc

    flagsmith = Flagsmith(
        environment_key=environment_key,
        enable_events=True,
        # Large buffer: with max_buffer_items=1 the worker drops the oldest
        # event whenever the buffer fills, so a rapid 300-user loop loses
        # exposures. 1000 holds the whole run; the final flush sends it.
        event_processor_config=EventProcessorConfig(
            max_buffer_items=1000, flush_interval_seconds=10
        ),
    )
    rng = random.Random(seed)
    summary = SimulationSummary(
        users=users, seed=seed,
        control_exposures=0, control_conversions=0,
        variant_exposures=0, variant_conversions=0,
    )
    try:
        for n in range(1, users + 1):
            identifier = f"sim-{n:03d}"
            flag = flagsmith.get_experiment_flag(FLAG_NAME, identifier=identifier)
            variant_key = getattr(flag, "variant", None) or "control"
            if variant_key == "control":
                summary.control_exposures += 1
            else:
                summary.variant_exposures += 1
            rate = CONTROL_RATE if variant_key == "control" else VARIANT_RATE
            if rng.random() < rate:
                flagsmith.track_event(METRIC_EVENT, identifier=identifier)
                if variant_key == "control":
                    summary.control_conversions += 1
                else:
                    summary.variant_conversions += 1
            if n % 50 == 0:
                print_fn(f"  ... {n}/{users} shoppers simulated")
    finally:
        # Flush buffered events before exit.
        flush = getattr(flagsmith, "flush_events", None) or getattr(
            flagsmith, "flush", None
        )
        if callable(flush):
            flush()
    return summary
