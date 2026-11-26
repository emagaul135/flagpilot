"""Plan + approval tests (spec §8).

- The plan renders every fact a human needs to approve.
- Answering anything except ``y`` stops the run with zero CLI calls
  (asserted on the dry-run log of the client the run actually used).
- Answering ``y`` at every gate runs the full dry-run loop in order.
"""

import pytest

from flagpilot import cli as cli_mod
from flagpilot.client import FlagsmithClient
from flagpilot.parse import CANONICAL_SPEC
from flagpilot.plan import ask_approval, render_plan

CANONICAL_PROMPT = (
    "Test the checkout button copy: 'Buy now' vs 'Get yours today'. "
    "Success is a purchase."
)


def test_plan_renders_everything():
    plan = render_plan(CANONICAL_SPEC)
    assert "checkout_button" in plan
    assert "Buy now" in plan
    assert "Get yours today" in plan
    assert "control" in plan and "get_yours" in plan
    assert "purchase" in plan
    assert "Checkout button copy — Nov 2026" in plan
    assert "Get yours today' button converts" in plan
    assert "50%" in plan and "100%" in plan
    assert "demo/flagpilot-config.json" in plan


@pytest.mark.parametrize("answer,expected", [
    ("y", True),
    ("Y", True),
    ("  y  ", True),
    ("n", False),
    ("yes", False),   # only an exact `y` counts
    ("", False),
    ("no", False),
])
def test_ask_approval_only_exact_y_counts(answer, expected, capsys):
    assert ask_approval(input_fn=lambda _: answer) is expected


def test_ask_approval_eof_is_refusal():
    def eof_input(_):
        raise EOFError

    assert ask_approval(input_fn=eof_input) is False


def _recording_client(monkeypatch):
    """Patch cli.FlagsmithClient so the test can inspect the exact client
    the run used."""
    created = []

    class RecordingClient(FlagsmithClient):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            created.append(self)

    monkeypatch.setattr(cli_mod, "FlagsmithClient", RecordingClient)
    return created


def test_refusal_at_plan_approval_makes_zero_cli_calls(monkeypatch, capsys):
    created = _recording_client(monkeypatch)
    monkeypatch.setattr("builtins.input", lambda _: "n")
    rc = cli_mod.main(["run", CANONICAL_PROMPT, "--dry-run"])
    assert rc == 0
    assert len(created) == 1
    assert created[0].log == []  # zero CLI calls
    out = capsys.readouterr().out
    assert "Stopped" in out
    assert "[dry-run]" not in out
    assert "checkout_button" in out  # the plan was still printed


def test_refusal_at_second_gate_makes_no_write_calls(monkeypatch, capsys):
    created = _recording_client(monkeypatch)
    # y (plan) then n (flag creation).
    answers = iter(["y", "n"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    rc = cli_mod.main(["run", CANONICAL_PROMPT, "--dry-run"])
    assert rc == 0
    # Only the read-only connection checks ran; no flag/metric writes.
    # (The warehouse-connections check runs because flagsmith.json supplies
    # an environment key — it is a GET, not a write. The key is read from
    # the file so the test stays true after `flagsmith init` fills it in.)
    import json
    from pathlib import Path

    env_key = json.loads(
        (Path(__file__).parent.parent / "flagsmith.json").read_text()
    )["environment_key"]
    assert created[0].log == [
        "flagsmith --version",
        "flagsmith auth status",
        f"flagsmith api api/v1/environments/{env_key}/"
        "warehouse-connections/ --method GET",
    ]
    assert not any("feature create" in c for c in created[0].log)
    assert not any("variant add" in c for c in created[0].log)
    out = capsys.readouterr().out
    assert "feature create" not in out


def test_full_dry_run_approvals_run_steps_in_order(monkeypatch, capsys):
    created = _recording_client(monkeypatch)
    monkeypatch.setattr("builtins.input", lambda _: "y")
    rc = cli_mod.main(["run", CANONICAL_PROMPT, "--dry-run"])
    assert rc == 0
    log = created[0].log
    # Steps in order: checks, flag create, variants, verify, metric,
    # experiment, start.
    assert log[0] == "flagsmith --version"
    assert log[1] == "flagsmith auth status"
    assert "flagsmith feature create checkout_button --value control --enabled" in log
    assert "flagsmith feature variant add checkout_button --value Buy now --key control --weight 0" in log
    assert "flagsmith feature variant add checkout_button --value Get yours today --key get_yours --weight 0" in log
    assert "flagsmith feature get checkout_button --json" in log
    assert any("experiment-metrics" in c and "purchase" in c for c in log)
    assert any("/experiments/" in c and "checkout_button" not in c for c in log)
    assert any("/experiments/0/start/" in c for c in log)
    # Order: flag before metric before experiment before start.
    idx = {name: next(i for i, c in enumerate(log) if name in c)
           for name in ["feature create", "experiment-metrics",
                        "/experiments/", "/start/"]}
    assert idx["feature create"] < idx["experiment-metrics"] < idx["/experiments/"] < idx["/start/"]
    out = capsys.readouterr().out
    assert "Experiment is running" in out
