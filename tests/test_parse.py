"""Parser tests (spec §8): the canonical prompt → the exact §4 spec;
a prompt with no variations / no success event → the agent asks the
three questions instead of guessing; the LLM path is never required.
No network, no Flagsmith account needed.
"""

from flagpilot.parse import (
    CANONICAL_SPEC,
    QUESTIONS,
    ask_clarifying_questions,
    parse_prompt,
    parse_template,
    parse_with_llm,
)

CANONICAL_PROMPT = (
    "Test the checkout button copy: 'Buy now' vs 'Get yours today'. "
    "Success is a purchase."
)


def test_canonical_prompt_produces_exact_spec():
    spec = parse_template(CANONICAL_PROMPT)
    assert spec is not None
    assert spec.flag == "checkout_button"
    assert [v.value for v in spec.variations] == ["Buy now", "Get yours today"]
    assert [v.key for v in spec.variations] == ["control", "get_yours"]
    assert spec.metric_name == "purchase"
    assert spec.metric_event == "purchase"
    assert spec.split_percentages == [50, 50]
    assert spec.rollout_percentage == 100
    assert spec.hypothesis == (
        "The 'Get yours today' button converts more shoppers "
        "than 'Buy now'."
    )
    assert spec.experiment_name == "Checkout button copy — Nov 2026"
    assert spec == CANONICAL_SPEC


def test_canonical_prompt_variants_of_phrasing():
    # Double quotes, no quotes, "Success is purchase" (no article).
    for prompt in [
        'Test checkout button: "Buy now" vs "Get yours today". Success is purchase.',
        "Test the checkout button copy: Buy now vs Get yours today. Success is a purchase.",
        "Test checkout button copy: 'Buy now' vs 'Get yours today'. Success is a purchase",
    ]:
        spec = parse_template(prompt)
        assert spec is not None, prompt
        assert spec.flag == "checkout_button"
        assert spec.metric_event == "purchase"


def test_non_canonical_prompt_builds_generic_spec():
    spec = parse_template(
        "Test the headline: 'Free shipping' vs 'Ships today'. "
        "Success is a signup."
    )
    assert spec is not None
    assert spec.flag == "headline"
    assert [v.value for v in spec.variations] == ["Free shipping", "Ships today"]
    # Each variation's key comes from its own value; the first is control.
    assert [v.key for v in spec.variations] == ["control", "ships_today"]
    assert spec.metric_event == "signup"


def test_unparseable_prompt_returns_none():
    assert parse_template("make the button nicer") is None
    assert parse_template("Test the checkout button copy") is None
    # Variations but no success event -> no guessing.
    assert parse_template(
        "Test the checkout button: 'Buy now' vs 'Get yours today'."
    ) is None
    # Success event but no variations -> no guessing.
    assert parse_template("Test the checkout button. Success is a purchase.") is None


def test_llm_path_returns_none_without_key():
    assert parse_with_llm(CANONICAL_PROMPT) is None
    assert parse_with_llm(CANONICAL_PROMPT, api_key=None) is None


def test_bad_prompt_asks_the_three_questions():
    answers = iter([
        "the checkout button copy: 'Buy now' vs 'Get yours today'",
        "a purchase",
        "flagpilot / production",
    ])
    asked = []

    def fake_input(prompt):
        asked.append(prompt)
        return next(answers)

    spec = parse_prompt(
        "make the button nicer", input_fn=fake_input, print_fn=lambda _: None
    )
    assert spec.flag == "checkout_button"
    assert spec.metric_event == "purchase"
    # All three questions were asked.
    assert any("What do you want to test" in q for q in asked)
    assert any("What counts as success" in q for q in asked)
    assert any("Which project and environment" in q for q in asked)
    assert len(QUESTIONS) == 3


def test_questions_fall_back_to_explicit_variants():
    answers = iter([
        "the checkout button copy",  # no variants in this answer
        "a purchase",
        "",
        "'Buy now' vs 'Get yours today'",  # explicit variants on re-ask
    ])

    def fake_input(prompt):
        return next(answers)

    spec = ask_clarifying_questions(
        input_fn=fake_input, print_fn=lambda _: None
    )
    assert spec.flag == "checkout_button"
    assert [v.value for v in spec.variations] == ["Buy now", "Get yours today"]


def test_questions_with_plain_variants_builds_spec():
    answers = iter(["the button", "a purchase", "", "nicer vs nicer-er"])

    def fake_input(prompt):
        return next(answers)

    # "nicer vs nicer-er" (no quotes) parses as variants of "the button".
    spec = ask_clarifying_questions(
        input_fn=fake_input, print_fn=lambda _: None
    )
    assert spec.flag == "button"
