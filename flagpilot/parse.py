"""Prompt parsing for FlagPilot.

Two paths (spec §2, step 1):

1. LLM path (preferred, optional): Google Gemini via ``GEMINI_API_KEY``.
   Stubbed here — the import is guarded and the path is never required.
   The template parser below always works, so the agent runs end to end
   with no LLM key at all.
2. Deterministic template parser for the canonical phrasings
   ("Test X: A vs B. Success is Y.") plus the three interactive
   clarifying questions from the official Flagsmith coding-agent prompt
   when the prompt does not parse: what to test, what counts as success,
   which project/environment.

The canonical demo spec (spec §4) is exact:

- flag ``checkout_button``, enabled, value ``control``
- control: value ``Buy now``, key ``control``
- variant: value ``Get yours today``, key ``get_yours``
- split 50/50, rollout 100%
- metric: name ``purchase``, event ``purchase``, aggregation
  ``occurrence``, direction ``up``
- experiment: name ``Checkout button copy — Nov 2026``,
  hypothesis ``The 'Get yours today' button converts more shoppers
  than 'Buy now'.``
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from typing import Callable, Optional

# ---------------------------------------------------------------------------
# The spec
# ---------------------------------------------------------------------------


@dataclass
class Variation:
    """One multivariate variation of a flag. Every variation MUST have a
    key — one without a key records no exposures (official prompt, step 4).
    ``control`` is reserved for the flag's own value."""

    value: str
    key: str


@dataclass
class ExperimentSpec:
    """Everything the agent needs to create the flag, metric and
    experiment. Human-readable in one screen."""

    flag: str
    variations: list[Variation]
    metric_name: str
    metric_event: str
    hypothesis: str
    experiment_name: str
    rollout_percentage: int = 100
    # Per-variation percentage allocation; control gets the rest.
    split_percentages: list[int] = field(default_factory=lambda: [50, 50])
    project: str = "flagpilot"
    environment: str = "production"

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


# The exact §4 demo spec.
CANONICAL_SPEC = ExperimentSpec(
    flag="checkout_button",
    variations=[
        Variation(value="Buy now", key="control"),
        Variation(value="Get yours today", key="get_yours"),
    ],
    metric_name="purchase",
    metric_event="purchase",
    hypothesis=(
        "The 'Get yours today' button converts more shoppers "
        "than 'Buy now'."
    ),
    experiment_name="Checkout button copy — Nov 2026",
    rollout_percentage=100,
    split_percentages=[50, 50],
)

# ---------------------------------------------------------------------------
# LLM path (stub — guarded import, never required)
# ---------------------------------------------------------------------------


def parse_with_llm(prompt: str, api_key: Optional[str] = None) -> Optional[ExperimentSpec]:
    """Parse a prompt with Gemini. Returns ``None`` when the path is
    unavailable (no key, or ``google-generativeai`` not installed) so the
    caller falls back to the deterministic template parser.

    The LLM is instructed to return ONLY a JSON spec with the keys
    ``flag``, ``variations`` (each ``{value, key}``), ``metric_event``,
    ``hypothesis`` and ``rollout_percentage``. Two hard rules are in the
    prompt: every variation needs a key, and ``control`` is reserved for
    the flag's own value.

    NOT implemented in this scaffold: the build window wires this up on
    Day 1 only if a free Gemini key is available. The agent never depends
    on it.
    """
    if not api_key:
        return None
    try:
        import google.generativeai  # type: ignore  # noqa: F401
    except ImportError:
        return None
    # LLM path not wired in the scaffold — template parser is the demo path.
    raise NotImplementedError(
        "LLM parsing is stubbed in the scaffold. Set up the Gemini call "
        "on Day 1 of the build window, or use the template parser."
    )


# ---------------------------------------------------------------------------
# Deterministic template parser
# ---------------------------------------------------------------------------

# Canonical phrasings, e.g.:
#   Test the checkout button copy: 'Buy now' vs 'Get yours today'.
#   Success is a purchase.
#   Test checkout button: "Buy now" vs "Get yours today". Success is purchase.
_VS_RE = re.compile(
    r"""
    ^\s*(?:test\s+(?:the\s+)?)?          # optional leading "Test (the)"
    (?P<thing>.+?)                        # what is being tested
    \s*:\s*
    (?P<a>[\"']?)(?P<val_a>.+?)(?P=a)     # variant A, quotes optional
    \s+vs\.?\s+
    (?P<b>[\"']?)(?P<val_b>.+?)(?P=b)     # variant B, quotes optional
    \s*\.?\s*$
    """,
    re.IGNORECASE | re.VERBOSE,
)

_SUCCESS_RE = re.compile(
    r"""
    success\s+is\s+(?:a\s+|an\s+|the\s+)?   # "Success is (a|an|the)"
    (?P<event>[A-Za-z][A-Za-z0-9 _-]*?)      # the event, e.g. "purchase"
    \s*\.?\s*$
    """,
    re.IGNORECASE | re.VERBOSE,
)


def _slug(text: str) -> str:
    """'checkout button copy' -> 'checkout_button'."""
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")


def _event_name(text: str) -> str:
    """'a purchase' -> 'purchase'."""
    return _slug(text)


def _key_for(value: str, index: int) -> str:
    """First variation is the control; later ones get a slug key."""
    if index == 0:
        return "control"
    return _slug(value)


def parse_template(prompt: str) -> Optional[ExperimentSpec]:
    """Parse the canonical phrasings into an :class:`ExperimentSpec`.

    Returns ``None`` when the prompt does not match — the caller must ask
    the three clarifying questions instead of guessing.
    """
    # Split "Test X: A vs B. Success is Y." into its two sentences.
    parts = re.split(r"\.\s*", prompt.strip(), maxsplit=1)
    head = parts[0].strip()
    tail = parts[1].strip() if len(parts) > 1 else ""

    vs = _VS_RE.match(head)
    if not vs:
        return None
    success = _SUCCESS_RE.search(tail) if tail else None
    if not success:
        return None

    thing = vs.group("thing").strip()
    val_a = vs.group("val_a").strip()
    val_b = vs.group("val_b").strip()
    event = _event_name(success.group("event"))

    # The canonical demo scenario maps to the exact §4 spec. Anything else
    # gets a spec built the same way, with the same shape.
    if (
        _slug(thing) in ("checkout_button", "checkout_button_copy")
        and val_a == "Buy now"
        and val_b == "Get yours today"
        and event == "purchase"
    ):
        return CANONICAL_SPEC

    variations = [
        Variation(value=val_a, key=_key_for(val_a, 0)),
        Variation(value=val_b, key=_key_for(val_b, 1)),
    ]
    return ExperimentSpec(
        flag=_slug(thing),
        variations=variations,
        metric_name=event,
        metric_event=event,
        hypothesis=(
            f"The '{val_b}' variant converts more than '{val_a}' "
            f"for {thing}."
        ),
        experiment_name=f"{thing.strip().capitalize()} — experiment",
        rollout_percentage=100,
        split_percentages=[50, 50],
    )


# ---------------------------------------------------------------------------
# The three clarifying questions
# ---------------------------------------------------------------------------

QUESTION_TEST = (
    "What do you want to test? "
    "(e.g. the checkout button copy: 'Buy now' vs 'Get yours today')"
)
QUESTION_SUCCESS = "What counts as success? (e.g. a purchase)"
QUESTION_PROJECT_ENV = (
    "Which project and environment? "
    "(e.g. flagpilot / production — press Enter for the defaults)"
)

QUESTIONS = (QUESTION_TEST, QUESTION_SUCCESS, QUESTION_PROJECT_ENV)


def ask_clarifying_questions(
    input_fn: Callable[[str], str] | None = None,
    print_fn: Callable[[str], None] | None = None,
) -> ExperimentSpec:
    """Ask the three questions from the official prompt and build a spec
    from the answers. Never guesses: if the "what to test" answer still
    has no variants, it asks once more for the two variants in
    ``'A' vs 'B'`` form.
    """
    if input_fn is None:
        input_fn = input
    if print_fn is None:
        print_fn = print
    print_fn("I couldn't parse that prompt, so let me ask a few questions.")

    test_answer = input_fn(QUESTION_TEST + "\n> ").strip()
    success_answer = input_fn(QUESTION_SUCCESS + "\n> ").strip()
    project_env = input_fn(QUESTION_PROJECT_ENV + "\n> ").strip()

    # Re-use the template parser on the "what to test" answer, with and
    # without the leading "Test".
    probe = test_answer if test_answer.lower().startswith("test") else f"Test {test_answer}"
    spec = parse_template(f"{probe}. Success is {success_answer}.")
    if spec is None:
        # Still no variants — ask once, explicitly, for "A vs B".
        variants_answer = input_fn(
            "What are the two variants? (e.g. 'Buy now' vs 'Get yours today')\n> "
        ).strip()
        combined = f"Test {test_answer}: {variants_answer}. Success is {success_answer}."
        spec = parse_template(combined)
    if spec is None:
        raise ValueError(
            "Still couldn't parse the experiment from those answers. "
            "Try the canonical phrasing: "
            "Test X: 'A' vs 'B'. Success is Y."
        )

    if project_env:
        parts = re.split(r"[/\s]+", project_env.strip(), maxsplit=1)
        spec.project = parts[0]
        if len(parts) > 1:
            spec.environment = parts[1]
    return spec


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def parse_prompt(
    prompt: str,
    llm_api_key: Optional[str] = None,
    input_fn: Callable[[str], str] | None = None,
    print_fn: Callable[[str], None] | None = None,
) -> ExperimentSpec:
    """Parse a prompt into a spec.

    Tries the LLM path first when a key is given, then the deterministic
    template parser, then the three clarifying questions. Never guesses.
    """
    if llm_api_key:
        try:
            llm_spec = parse_with_llm(prompt, api_key=llm_api_key)
        except NotImplementedError:
            llm_spec = None
        if llm_spec is not None:
            return llm_spec

    spec = parse_template(prompt)
    if spec is not None:
        return spec
    return ask_clarifying_questions(input_fn=input_fn, print_fn=print_fn)
