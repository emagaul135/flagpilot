"""Plan rendering + approval gates for FlagPilot (spec §2, step 2).

The agent prints the full plan — the exact flag, the exact variants with
keys, the exact metric, the exact experiment (name, hypothesis, rollout)
and the exact code/config change for the demo shop — then asks
``Approve this plan? [y/n]``. Answering anything except ``y`` stops the
run with a clean message and zero writes.

There is deliberately no ``--yes`` / auto-approve flag in the demo path:
approval is a Track 02 judging criterion, so the agent must visibly ask.
"""

from __future__ import annotations

from typing import Callable

from .parse import ExperimentSpec


def render_plan(spec: ExperimentSpec) -> str:
    """The full plan, readable in one screen."""
    lines = [
        "FlagPilot plan",
        "==============",
        "",
        f"Flag:        {spec.flag}  (multivariate, enabled, value 'control')",
        "Variants:",
    ]
    for i, var in enumerate(spec.variations):
        split = spec.split_percentages[i] if i < len(spec.split_percentages) else 0
        lines.append(f"  - {var.key}: {var.value!r}  ({split}% of traffic)")
    lines += [
        "",
        f"Metric:      {spec.metric_name}  (event '{spec.metric_event}', "
        "aggregation 'occurrence', direction 'up')",
        f"Experiment:  {spec.experiment_name}",
        f"Hypothesis:  {spec.hypothesis}",
        f"Rollout:     {spec.rollout_percentage}%",
        "",
        "Demo shop:   write demo/flagpilot-config.json with this flag, "
        "these variants and this metric event.",
        "",
        "Steps the agent will take (each asks again before it writes):",
        "  1. create the flag + variants (flagsmith CLI)",
        "  2. create the metric + the experiment (flagsmith api)",
        "  3. write the demo config",
        "  4. start the experiment",
        "",
    ]
    return "\n".join(lines)


def ask_approval(
    question: str = "Approve this plan? [y/n] ",
    input_fn: Callable[[str], str] | None = None,
    print_fn: Callable[[str], None] | None = None,
) -> bool:
    """Ask for approval. Only an exact ``y`` (case-insensitive) counts.

    Anything else — ``n``, ``yes``, an empty line, EOF — is a refusal and
    stops the run with zero writes.
    """
    if input_fn is None:
        input_fn = input
    if print_fn is None:
        print_fn = print
    try:
        answer = input_fn(question)
    except EOFError:
        answer = ""
    approved = answer.strip().lower() == "y"
    if not approved:
        print_fn("Stopped — no changes were made to Flagsmith.")
    return approved


class ApprovalRefused(Exception):
    """Raised when the human refuses a step, so the run stops cleanly."""


def require_approval(
    question: str,
    input_fn: Callable[[str], str] | None = None,
    print_fn: Callable[[str], None] | None = None,
) -> None:
    """Ask for approval; raise :class:`ApprovalRefused` on any refusal."""
    if not ask_approval(question, input_fn=input_fn, print_fn=print_fn):
        raise ApprovalRefused(question)
