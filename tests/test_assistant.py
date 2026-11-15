"""Tests for the 'Ask about your fund' helper. The Claude API is replaced by a fake network
connection that records the exact request and plays back a canned streamed answer."""

import json

import anthropic
import httpx2
import pytest

from engine import assistant
from engine.assistant import AssistantError

BUILD = {
    "preferences": {"ai": "want", "oil": "avoid"},
    "holdings": [{"ticker": "NVDA", "weight_pct": 60.0, "tiers": {"AI": "High", "Oil": "Limited"}, "labels": []},
                 {"ticker": "CASH", "weight_pct": 40.0, "tiers": None, "labels": []}],
    "cash_pct": 40.0, "warnings": ["Only 1 holding."], "rejected_by_etf_check": [],
    "verification": {"all_pass": True, "checks": {"ai": {"theme": "AI", "choice": "want", "goal": "g",
                                                          "pass": True, "sentence": "All AI."}}},
}
RISK = {
    "monte_carlo": {"n_paths": 5000, "block_days": 5, "history_start": "2024-11-18", "history_end": "2026-11-13",
                    "seed": 20261115, "portfolio": {"var_5": 0.123456789}, "benchmark": {"var_5": 0.1},
                    "p_beat_benchmark": 0.5, "sentences": ["S1"], "fan": {"days": list(range(253))}},
    "shocks": [{"theme_name": "Oil", "portfolio_move": -0.01, "sentence": "If oil producers rose..."}],
    "frontier": {"available": True, "sentences": ["MV."]},
    "summary": ["In short."],
}


# ---- facts and prompt ----

def test_fund_facts_carry_what_questions_need_and_drop_raw_arrays():
    facts = assistant.fund_facts(BUILD, RISK)
    assert facts["fund_built"] is True
    assert facts["holdings"][0] == {"ticker": "NVDA", "weight_pct": 60.0,
                                    "tiers": {"AI": "High", "Oil": "Limited"}, "labels": []}
    assert facts["rescreen"]["all_goals_met"] is True
    assert facts["monte_carlo"]["portfolio"]["var_5"] == 0.1235
    assert "fan" not in json.dumps(facts) and "253" not in json.dumps(facts)
    assert facts["theme_shocks_plus_30pct"][0]["theme"] == "Oil"
    assert facts["on_chain"]["launched"] is False


def test_fund_facts_without_a_fund():
    facts = assistant.fund_facts(None)
    assert facts["fund_built"] is False and "holdings" not in facts and "monte_carlo" not in facts


def test_system_prompt_rules_first_and_facts_cached():
    blocks = assistant.system_blocks(assistant.fund_facts(BUILD, RISK, {"launched": True, "address": "0xabc"}))
    assert blocks[0]["text"] == assistant.SYSTEM_RULES and "cache_control" not in blocks[0]
    assert blocks[1]["cache_control"] == {"type": "ephemeral"} and '"address": "0xabc"' in blocks[1]["text"]
    rules = assistant.SYSTEM_RULES
    for must in ("ONLY from the FUND FACTS", "Not determined", "not a forecast",
                 "estimated sensitivity based on past co-movement", "never tell someone to buy"):
        assert must in rules


def test_same_facts_give_byte_identical_prompt():
    """A stable prompt is what lets the facts block be cached between questions."""
    a = assistant.system_blocks(assistant.fund_facts(BUILD, RISK))
    b = assistant.system_blocks(assistant.fund_facts(dict(reversed(list(BUILD.items()))), RISK))
    assert a == b


def test_build_messages_history_rules():
    history = [{"role": "assistant", "content": "orphan"}, {"role": "system", "content": "x"},
               {"role": "user", "content": "q1"}, {"role": "assistant", "content": "a1"},
               {"role": "user", "content": ""}]
    msgs = assistant.build_messages("  q2 ", history)
    assert msgs == [{"role": "user", "content": "q1"}, {"role": "assistant", "content": "a1"},
                    {"role": "user", "content": "q2"}]
    long = [{"role": r, "content": f"{r}{i}"} for i in range(30) for r in ("user", "assistant")]
    assert len(assistant.build_messages("q", long)) == 2 * assistant.MAX_HISTORY_TURNS + 1


@pytest.mark.parametrize("question, message", [("", "Type a question"), ("   ", "Type a question"),
                                               (None, "Type a question"), ("x" * 2001, "under 2,000")])
def test_bad_questions(question, message):
    with pytest.raises(AssistantError, match=message):
        assistant.build_messages(question)


# ---- client setup ----

def test_missing_key_is_a_clear_message(monkeypatch, tmp_path):
    monkeypatch.setattr(assistant, "ROOT", tmp_path)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(AssistantError, match="needs ANTHROPIC_API_KEY"):
        assistant.make_client()


def test_client_ignores_a_base_url_meant_for_another_tool(monkeypatch, tmp_path):
    monkeypatch.setattr(assistant, "ROOT", tmp_path)
    (tmp_path / ".env").write_text("ANTHROPIC_API_KEY=test-key\n")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "http://some-other-tool.local")
    client = assistant.make_client()
    assert str(client.base_url).rstrip("/") == "https://api.anthropic.com"


def test_client_base_url_can_be_set_in_project_env(monkeypatch, tmp_path):
    monkeypatch.setattr(assistant, "ROOT", tmp_path)
    (tmp_path / ".env").write_text("ANTHROPIC_API_KEY=test-key\nANTHROPIC_BASE_URL=http://gateway.local\n")
    assert str(assistant.make_client().base_url).rstrip("/") == "http://gateway.local"


# ---- the request and the streamed answer ----

def sse(text_chunks, stop_reason="end_turn"):
    events = [("message_start", {"type": "message_start", "message": {
        "id": "msg_1", "type": "message", "role": "assistant", "model": assistant.MODEL, "content": [],
        "stop_reason": None, "stop_sequence": None, "usage": {"input_tokens": 10, "output_tokens": 1}}}),
        ("content_block_start", {"type": "content_block_start", "index": 0,
                                 "content_block": {"type": "text", "text": ""}})]
    for chunk in text_chunks:
        events.append(("content_block_delta", {"type": "content_block_delta", "index": 0,
                                               "delta": {"type": "text_delta", "text": chunk}}))
    events += [("content_block_stop", {"type": "content_block_stop", "index": 0}),
               ("message_delta", {"type": "message_delta", "delta": {"stop_reason": stop_reason,
                                                                     "stop_sequence": None},
                                  "usage": {"output_tokens": 5}}),
               ("message_stop", {"type": "message_stop"})]
    return "".join(f"event: {e}\ndata: {json.dumps(d)}\n\n" for e, d in events).encode()


def fake_client(handler):
    transport = httpx2.MockTransport(handler)
    return anthropic.Anthropic(api_key="test-key", base_url="http://fake.claude", max_retries=0,
                               http_client=anthropic.DefaultHttpxClient(transport=transport))


def test_request_shape_and_streamed_answer():
    seen = {}

    def handler(request):
        seen["body"] = json.loads(request.content)
        seen["headers"] = request.headers
        return httpx2.Response(200, headers={"content-type": "text/event-stream"},
                               content=sse(["Your fund ", "holds NVDA."]))

    chunks = list(assistant.ask("What do I hold?", assistant.fund_facts(BUILD, RISK),
                                [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}],
                                client=fake_client(handler)))
    assert "".join(chunks) == "Your fund holds NVDA."
    body = seen["body"]
    assert body["model"] == "claude-opus-5-5" and body["stream"] is True
    assert body["fallbacks"] == "default"
    assert body["output_config"] == {"effort": "low"}
    assert body["max_tokens"] == assistant.MAX_TOKENS
    assert body["system"][1]["cache_control"] == {"type": "ephemeral"}
    assert body["messages"][-1] == {"role": "user", "content": "What do I hold?"}
    assert "thinking" not in body  # Claude Opus 5.5 always thinks; effort controls depth
    assert assistant.FALLBACK_BETA in seen["headers"]["anthropic-beta"]
    assert "test-key" in seen["headers"]["authorization"]  # the key travels in a header only


def test_refusal_gets_a_friendly_line():
    def handler(request):
        return httpx2.Response(200, headers={"content-type": "text/event-stream"},
                               content=sse([], stop_reason="refusal"))

    out = "".join(assistant.ask("q", {}, client=fake_client(handler)))
    assert out.startswith("I can't help with that one")


def test_cut_off_answer_is_flagged():
    def handler(request):
        return httpx2.Response(200, headers={"content-type": "text/event-stream"},
                               content=sse(["Part of an answer"], stop_reason="max_tokens"))

    out = "".join(assistant.ask("q", {}, client=fake_client(handler)))
    assert out.startswith("Part of an answer") and "cut off" in out


@pytest.mark.parametrize("status, error_type, message", [
    (401, "authentication_error", "key was rejected"),
    (403, "permission_error", "isn't allowed"),
    (429, "rate_limit_error", "busy right now"),
    (500, "api_error", "HTTP 500"),
])
def test_api_errors_become_plain_messages(status, error_type, message):
    def handler(request):
        return httpx2.Response(status, json={"type": "error", "error": {"type": error_type, "message": "x"}})

    with pytest.raises(AssistantError, match=message):
        list(assistant.ask("q", {}, client=fake_client(handler)))


@pytest.mark.parametrize("api_message, expected", [
    ("Your credit balance is too low to access the Anthropic API.", "out of credits"),
    ("messages: text content blocks must be non-empty", "couldn't process the request: messages: text"),
    ("", "couldn't process the request: bad request"),
])
def test_bad_request_explains_itself(api_message, expected):
    def handler(request):
        return httpx2.Response(400, json={"type": "error",
                                          "error": {"type": "invalid_request_error", "message": api_message}})

    with pytest.raises(AssistantError, match=expected):
        list(assistant.ask("q", {}, client=fake_client(handler)))


def test_network_failure_is_a_plain_message():
    def handler(request):
        raise httpx2.ConnectError("down")

    with pytest.raises(AssistantError, match="Couldn't reach Claude"):
        list(assistant.ask("q", {}, client=fake_client(handler)))


def test_unexpected_sdk_error_is_still_friendly():
    assert "failed (AnthropicError)" in str(assistant._friendly(anthropic.AnthropicError("boom")))
