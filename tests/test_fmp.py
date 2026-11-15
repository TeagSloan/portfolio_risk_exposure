"""Tests for the FMP client. The internet is replaced with fake responses and the cache
goes to a temporary folder, so these never call FMP or touch the real cache."""

import datetime as dt
import json
import os

import pandas as pd
import pytest
import requests

from engine import fmp


class FakeResponse:
    def __init__(self, status_code=200, payload=None, bad_json=False):
        self.status_code = status_code
        self._payload = payload
        self._bad_json = bad_json

    def json(self):
        if self._bad_json:
            raise ValueError("not json")
        return self._payload


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    """Temporary cache, a dummy key, and no real waiting between retries."""
    monkeypatch.setattr(fmp, "CACHE_DIR", tmp_path / "fmp")
    monkeypatch.setenv("FMP_API_KEY", "test-key")
    monkeypatch.setattr(fmp.time, "sleep", lambda s: None)


@pytest.fixture
def fake(monkeypatch):
    """Replace requests.get. Queue replies per endpoint with fake.replies[path] = [...]."""

    class Fake:
        def __init__(self):
            self.replies = {}
            self.calls = []

        def __call__(self, url, params=None, headers=None, timeout=None):
            path = url.replace(fmp.BASE_URL, "")
            self.calls.append({"path": path, "params": params, "headers": headers, "url": url})
            queue = self.replies[path]
            return queue.pop(0) if len(queue) > 1 else queue[0]

    f = Fake()
    monkeypatch.setattr(fmp.requests, "get", f)
    return f


# ---- key handling ----

def test_key_sent_in_header_never_in_url_params_or_cache(fake):
    fake.replies["profile"] = [FakeResponse(payload=[{"symbol": "NVDA"}])]
    fmp.get("profile", {"symbol": "NVDA"})
    call = fake.calls[0]
    assert call["headers"] == {"apikey": "test-key"}
    assert "test-key" not in call["url"] and "test-key" not in json.dumps(call["params"])
    cached = list(fmp.CACHE_DIR.glob("*.json"))
    assert len(cached) == 1 and "test-key" not in cached[0].read_text()


@pytest.mark.parametrize("value", ["", "   "])
def test_missing_key(monkeypatch, fake, value):
    monkeypatch.setenv("FMP_API_KEY", value)
    with pytest.raises(fmp.FMPError, match="No FMP API key"):
        fmp.get("profile", {"symbol": "NVDA"})


def test_unset_key(monkeypatch, fake):
    monkeypatch.delenv("FMP_API_KEY")
    with pytest.raises(fmp.FMPError, match="No FMP API key"):
        fmp.get("profile", {"symbol": "NVDA"})


# ---- cache ----

def test_second_call_uses_cache(fake):
    fake.replies["profile"] = [FakeResponse(payload=[{"symbol": "NVDA"}])]
    first = fmp.get("profile", {"symbol": "NVDA"})
    second = fmp.get("profile", {"symbol": "NVDA"})
    assert first == second == [{"symbol": "NVDA"}]
    assert len(fake.calls) == 1


def test_refresh_bypasses_cache(fake):
    fake.replies["profile"] = [FakeResponse(payload=[{"v": 1}]), FakeResponse(payload=[{"v": 2}])]
    assert fmp.get("profile", {"symbol": "X"}) == [{"v": 1}]
    assert fmp.get("profile", {"symbol": "X"}, refresh=True) == [{"v": 2}]
    assert fmp.get("profile", {"symbol": "X"}) == [{"v": 2}]  # cache updated
    assert len(fake.calls) == 2


def test_different_params_cached_separately(fake):
    fake.replies["profile"] = [FakeResponse(payload=[{"s": "A"}]),
                               FakeResponse(payload=[{"s": "B"}])]
    assert fmp.get("profile", {"symbol": "A"}) == [{"s": "A"}]
    assert fmp.get("profile", {"symbol": "B"}) == [{"s": "B"}]
    assert len(list(fmp.CACHE_DIR.glob("*.json"))) == 2


def test_param_order_does_not_matter(fake):
    fake.replies["x"] = [FakeResponse(payload=[1])]
    fmp.get("x", {"a": 1, "b": 2})
    fmp.get("x", {"b": 2, "a": 1})
    assert len(fake.calls) == 1


def test_empty_answers_not_cached(fake):
    fake.replies["profile"] = [FakeResponse(payload=[]), FakeResponse(payload=[{"s": "A"}])]
    assert fmp.get("profile", {"symbol": "A"}) == []
    assert fmp.get("profile", {"symbol": "A"}) == [{"s": "A"}]
    assert len(fake.calls) == 2


def test_cache_file_records_what_was_asked(fake):
    fake.replies["historical-price-eod/dividend-adjusted"] = [FakeResponse(payload=[1])]
    fmp.get("historical-price-eod/dividend-adjusted", {"symbol": "XOM"})
    record = json.loads(next(fmp.CACHE_DIR.glob("*.json")).read_text())
    assert record["path"] == "historical-price-eod/dividend-adjusted"
    assert record["params"] == {"symbol": "XOM"} and "fetched_at" in record


# ---- errors and retries ----

@pytest.mark.parametrize(
    "status, message",
    [(401, "rejected the API key"), (403, "rejected the API key"),
     (402, "not included in your FMP plan"), (404, "HTTP 404")],
)
def test_http_errors(fake, status, message):
    fake.replies["profile"] = [FakeResponse(status_code=status)]
    with pytest.raises(fmp.FMPError, match=message):
        fmp.get("profile", {"symbol": "X"})
    assert len(fake.calls) == 1  # these are not retried


def test_rate_limit_retried_then_succeeds(fake):
    fake.replies["profile"] = [FakeResponse(status_code=429), FakeResponse(payload=[{"ok": 1}])]
    assert fmp.get("profile", {"symbol": "X"}) == [{"ok": 1}]
    assert len(fake.calls) == 2


def test_server_error_retried_then_gives_up(fake):
    fake.replies["profile"] = [FakeResponse(status_code=503)]
    with pytest.raises(fmp.FMPError, match="HTTP 503"):
        fmp.get("profile", {"symbol": "X"})
    assert len(fake.calls) == 1 + len(fmp.RETRY_WAITS_SECONDS)


def test_rate_limit_that_never_clears(fake):
    fake.replies["profile"] = [FakeResponse(status_code=429)]
    with pytest.raises(fmp.FMPError, match="rate limit"):
        fmp.get("profile", {"symbol": "X"})


def test_network_failure(monkeypatch):
    def boom(*args, **kwargs):
        raise requests.ConnectionError("down")

    monkeypatch.setattr(fmp.requests, "get", boom)
    with pytest.raises(fmp.FMPError, match="Could not reach FMP"):
        fmp.get("profile", {"symbol": "X"})


def test_unreadable_reply(fake):
    fake.replies["profile"] = [FakeResponse(bad_json=True)]
    with pytest.raises(fmp.FMPError, match="unreadable"):
        fmp.get("profile", {"symbol": "X"})


@pytest.mark.parametrize("payload", [{"Error Message": "Invalid API KEY"}, {"error": "Limit"}])
def test_fmp_error_payloads(fake, payload):
    fake.replies["profile"] = [FakeResponse(payload=payload)]
    with pytest.raises(fmp.FMPError, match="FMP error for 'profile'"):
        fmp.get("profile", {"symbol": "X"})


# ---- endpoint helpers ----

@pytest.mark.parametrize("bad", ["", "  ", None, 5])
def test_bad_ticker_rejected_before_calling_fmp(fake, bad):
    with pytest.raises(fmp.FMPError, match="not a valid ticker"):
        fmp.profile(bad)
    assert fake.calls == []


def test_profile_normalizes_ticker(fake):
    fake.replies["profile"] = [FakeResponse(payload=[{"symbol": "NVDA", "sector": "Technology"}])]
    assert fmp.profile(" nvda ")["sector"] == "Technology"
    assert fake.calls[0]["params"] == {"symbol": "NVDA"}


def test_profile_unknown_ticker(fake):
    fake.replies["profile"] = [FakeResponse(payload=[])]
    with pytest.raises(fmp.FMPError, match="No company profile found for 'ZZZZ'"):
        fmp.profile("ZZZZ")


def test_segment_shares_use_latest_year(fake):
    fake.replies["revenue-product-segmentation"] = [FakeResponse(payload=[
        {"fiscalYear": 2025, "date": "2025-01-26", "data": {"Data Center": 50, "Gaming": 50}},
        {"fiscalYear": 2026, "date": "2026-01-25",
         "data": {"Gaming": 10, "Data Center": 90, "Note": "n/a"}},
    ])]
    result = fmp.latest_segment_shares("NVDA")
    assert result["fiscal_year"] == 2026 and result["total"] == 100
    assert result["shares"] == {"Data Center": 0.9, "Gaming": 0.1}
    assert list(result["shares"]) == ["Data Center", "Gaming"]  # largest first


def test_segment_shares_missing(fake):
    fake.replies["revenue-product-segmentation"] = [FakeResponse(payload=[])]
    with pytest.raises(fmp.FMPError, match="no segment revenue"):
        fmp.latest_segment_shares("SPY")


def test_segment_shares_all_zero(fake):
    fake.replies["revenue-product-segmentation"] = [FakeResponse(payload=[
        {"fiscalYear": 2026, "date": "2026-01-25", "data": {"A": 0}}])]
    with pytest.raises(fmp.FMPError, match="adds up to zero"):
        fmp.latest_segment_shares("X")


def test_income_statement_and_screener_params(fake):
    fake.replies["income-statement"] = [FakeResponse(payload=[{"revenue": 1}])]
    fake.replies["company-screener"] = [FakeResponse(payload=[{"symbol": "XOM"}])]
    assert fmp.income_statement("xom", limit=1) == [{"revenue": 1}]
    assert fmp.company_screener(sector="Energy", limit=3) == [{"symbol": "XOM"}]
    assert fake.calls[0]["params"] == {"symbol": "XOM", "period": "annual", "limit": 1}
    assert fake.calls[1]["params"] == {"sector": "Energy", "limit": 3}


def test_empty_income_statement_and_screener(fake):
    fake.replies["income-statement"] = [FakeResponse(payload=[])]
    fake.replies["company-screener"] = [FakeResponse(payload=[])]
    assert fmp.income_statement("X") == []
    assert fmp.company_screener(sector="None") == []


PRICES = "historical-price-eod/dividend-adjusted"


def test_adjusted_prices_sorted_oldest_first(fake):
    fake.replies[PRICES] = [FakeResponse(payload=[
        {"date": "2026-11-13", "adjClose": 170.59}, {"date": "2026-11-12", "adjClose": 168.0}])]
    prices = fmp.adjusted_prices("xom", dt.date(2024, 11, 1), dt.date(2026, 11, 14))
    assert prices.name == "XOM"
    assert prices.index.tolist() == [pd.Timestamp("2026-11-12"), pd.Timestamp("2026-11-13")]
    assert fake.calls[0]["params"] == {"symbol": "XOM", "from": "2024-11-01", "to": "2026-11-14"}


def test_adjusted_prices_unknown_ticker(fake):
    fake.replies[PRICES] = [FakeResponse(payload=[])]
    with pytest.raises(fmp.FMPError, match="No price history found for 'ZZZZ'"):
        fmp.adjusted_prices("ZZZZ", "2024-01-01", "2024-02-01")


@pytest.mark.parametrize("row", [{"date": "2026-01-02"}, {"adjClose": 1.0},
                                 {"date": "2026-01-02", "adjClose": "abc"}])
def test_adjusted_prices_malformed(fake, row):
    fake.replies[PRICES] = [FakeResponse(payload=[row])]
    with pytest.raises(fmp.FMPError, match="missing dates or prices"):
        fmp.adjusted_prices("X", "2026-01-01", "2026-02-01")


@pytest.mark.parametrize("bad", [0.0, -1.0])
def test_adjusted_prices_nonpositive(fake, bad):
    fake.replies[PRICES] = [FakeResponse(payload=[{"date": "2026-01-02", "adjClose": bad}])]
    with pytest.raises(fmp.FMPError, match="zero or negative"):
        fmp.adjusted_prices("X", "2026-01-01", "2026-02-01")


# ---- command-line endpoint check ----

def _all_endpoints_ok(fake):
    fake.replies["profile"] = [FakeResponse(payload=[
        {"companyName": "Exxon", "sector": "Energy", "industry": "Oil"}])]
    fake.replies["revenue-product-segmentation"] = [FakeResponse(payload=[
        {"fiscalYear": 2025, "date": "2025-12-31", "data": {"Upstream": 3, "Chemicals": 1}}])]
    fake.replies["income-statement"] = [FakeResponse(payload=[
        {"fiscalYear": "2025", "revenue": 3.2e11}])]
    fake.replies[PRICES] = [FakeResponse(payload=[
        {"date": "2026-11-12", "adjClose": 1.0}, {"date": "2026-11-13", "adjClose": 1.1}])]
    fake.replies["company-screener"] = [FakeResponse(payload=[{"symbol": "XOM"},
                                                              {"symbol": "CVX"}])]


def test_check_endpoints_all_ok(fake, capsys):
    _all_endpoints_ok(fake)
    assert fmp.main(["xom"]) == 0
    out = capsys.readouterr().out
    assert "FAIL" not in out
    assert "Upstream 75%" in out and "revenue $320.0B" in out and "2 days" in out
    assert "sector=Energy" in out and "XOM, CVX" in out


def test_check_endpoints_reports_failures(fake, capsys):
    _all_endpoints_ok(fake)
    fake.replies["revenue-product-segmentation"] = [FakeResponse(status_code=402)]
    fake.replies["income-statement"] = [FakeResponse(payload=[])]
    assert fmp.main(["XOM"]) == 1
    out = capsys.readouterr().out
    assert "FAIL revenue-product-segmentation" in out
    assert "no statements returned" in out


def test_check_runs_screener_once_per_sector(fake, capsys):
    _all_endpoints_ok(fake)
    fmp.main(["XOM", "CVX"])
    assert capsys.readouterr().out.count("company-screener") == 1


def test_check_skips_screener_when_profile_fails(fake, capsys):
    _all_endpoints_ok(fake)
    fake.replies["profile"] = [FakeResponse(payload=[])]
    assert fmp.main(["ZZZZ"]) == 1
    assert "company-screener" not in capsys.readouterr().out


def test_check_without_key_is_a_message_not_a_crash(monkeypatch, fake, capsys):
    _all_endpoints_ok(fake)
    monkeypatch.delenv("FMP_API_KEY")
    assert fmp.main(["XOM"]) == 1
    assert "FAIL" in capsys.readouterr().out


def test_main_defaults_to_nvda_and_xom(monkeypatch):
    seen = {}

    def fake_check(symbols):
        seen["symbols"] = symbols
        raise fmp.FMPError("stop here")

    monkeypatch.setattr(fmp, "check_endpoints", fake_check)
    monkeypatch.setattr(fmp.sys, "argv", ["fmp"])
    assert fmp.main() == 1
    assert seen["symbols"] == ["NVDA", "XOM"]


# ---- live check against real FMP (opt-in: RUN_LIVE=1) ----

@pytest.mark.live
@pytest.mark.skipif(os.environ.get("RUN_LIVE") != "1", reason="set RUN_LIVE=1 to call real FMP")
def test_live_all_endpoints_work_for_nvda_and_xom(monkeypatch, tmp_path):
    monkeypatch.undo()  # real key from .env, real requests
    fmp.load_dotenv(fmp.PROJECT_ROOT / ".env")
    monkeypatch.setattr(fmp, "CACHE_DIR", tmp_path / "fmp")
    results = fmp.check_endpoints(["NVDA", "XOM"])
    failures = [r for r in results if not r["ok"]]
    assert not failures, failures
