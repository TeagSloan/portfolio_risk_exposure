"""Tests for pulling data from FMP. The internet is replaced with fake responses."""

import datetime as dt

import pytest
import requests

from engine.mean_variance import data_fetcher
from engine.mean_variance.errors import DataFetchError


class FakeResponse:
    def __init__(self, status_code=200, payload=None, bad_json=False):
        self.status_code = status_code
        self._payload = payload
        self._bad_json = bad_json

    def json(self):
        if self._bad_json:
            raise ValueError("not json")
        return self._payload


@pytest.fixture
def fake_get(monkeypatch):
    """Replace requests.get. Set .responses[path] = FakeResponse to control replies."""

    class Recorder:
        def __init__(self):
            self.responses = {}
            self.calls = []

        def __call__(self, url, params=None, headers=None, timeout=None):
            self.calls.append({"url": url, "params": params, "headers": headers})
            path = url.replace(data_fetcher.BASE_URL + "/", "")
            reply = self.responses[path]
            if isinstance(reply, list):  # one reply per call, in order
                return reply.pop(0)
            return reply

    recorder = Recorder()
    monkeypatch.setattr(data_fetcher.requests, "get", recorder)
    return recorder


PRICES_PATH = "historical-price-eod/dividend-adjusted"
START, END = dt.date(2016, 9, 30), dt.date(2026, 10, 31)


# ---- API key ----

def test_api_key_passed_directly_wins(monkeypatch):
    monkeypatch.setenv("FMP_API_KEY", "from_env")
    assert data_fetcher.get_api_key("direct") == "direct"


def test_api_key_from_environment(monkeypatch):
    monkeypatch.setenv("FMP_API_KEY", "  from_env  ")
    assert data_fetcher.get_api_key() == "from_env"


@pytest.mark.parametrize("value", [None, "", "   "])
def test_missing_api_key_gives_clear_error(monkeypatch, value):
    monkeypatch.delenv("FMP_API_KEY", raising=False)
    if value is not None:
        monkeypatch.setenv("FMP_API_KEY", value)
    with pytest.raises(DataFetchError, match="No FMP API key"):
        data_fetcher.get_api_key()


# ---- HTTP handling ----

def test_key_sent_in_header_not_url(fake_get):
    fake_get.responses["x"] = FakeResponse(payload=[1])
    assert data_fetcher._get_json("x", {"symbol": "AAPL"}, "secret") == [1]
    call = fake_get.calls[0]
    assert call["headers"] == {"apikey": "secret"}
    assert "secret" not in str(call["params"]) and "secret" not in call["url"]


@pytest.mark.parametrize(
    "status, message",
    [(401, "rejected the API key"), (403, "rejected the API key"),
     (429, "rate limit"), (500, "HTTP 500")],
)
def test_http_errors_give_clear_messages(fake_get, status, message):
    fake_get.responses["x"] = FakeResponse(status_code=status)
    with pytest.raises(DataFetchError, match=message):
        data_fetcher._get_json("x", {}, "k")


def test_network_failure(monkeypatch):
    def boom(*args, **kwargs):
        raise requests.ConnectionError("down")

    monkeypatch.setattr(data_fetcher.requests, "get", boom)
    with pytest.raises(DataFetchError, match="Could not reach FMP"):
        data_fetcher._get_json("x", {}, "k")


def test_unreadable_reply(fake_get):
    fake_get.responses["x"] = FakeResponse(bad_json=True)
    with pytest.raises(DataFetchError, match="could not be read"):
        data_fetcher._get_json("x", {}, "k")


def test_fmp_error_message_passed_through(fake_get):
    fake_get.responses["x"] = FakeResponse(payload={"Error Message": "Invalid symbol"})
    with pytest.raises(DataFetchError, match="Invalid symbol"):
        data_fetcher._get_json("x", {}, "k")


# ---- Prices ----

def _rows(ticker, pairs):
    return [{"symbol": ticker, "date": d, "adjClose": p} for d, p in pairs]


def test_prices_one_column_per_ticker_with_gap_for_young_stock(fake_get):
    fake_get.responses[PRICES_PATH] = [
        FakeResponse(payload=_rows("OLD", [("2020-01-03", 11.0), ("2020-01-02", 10.0)])),
        FakeResponse(payload=_rows("NEW", [("2020-01-03", 5.0)])),
    ]
    prices = data_fetcher.fetch_adjusted_prices(["OLD", "NEW"], START, END, api_key="k")
    assert list(prices.columns) == ["OLD", "NEW"]
    assert prices["OLD"].tolist() == [10.0, 11.0]  # sorted oldest first
    assert prices["NEW"].isna().tolist() == [True, False]
    assert fake_get.calls[0]["params"] == {
        "symbol": "OLD", "from": "2016-09-30", "to": "2026-10-31"}


@pytest.mark.parametrize("payload", [[], {}, None])
def test_unknown_ticker(fake_get, payload):
    fake_get.responses[PRICES_PATH] = FakeResponse(payload=payload)
    with pytest.raises(DataFetchError, match="No price data found for 'ZZZZ'"):
        data_fetcher.fetch_adjusted_prices(["ZZZZ"], START, END, api_key="k")


@pytest.mark.parametrize(
    "row", [{"date": "2020-01-02"}, {"date": "2020-01-02", "adjClose": "abc"},
            {"adjClose": 10.0}],
)
def test_malformed_price_rows(fake_get, row):
    fake_get.responses[PRICES_PATH] = FakeResponse(payload=[row])
    with pytest.raises(DataFetchError, match="missing dates or prices"):
        data_fetcher.fetch_adjusted_prices(["X"], START, END, api_key="k")


@pytest.mark.parametrize("bad_price", [0.0, -5.0])
def test_zero_or_negative_prices_rejected(fake_get, bad_price):
    fake_get.responses[PRICES_PATH] = FakeResponse(
        payload=_rows("X", [("2020-01-02", 10.0), ("2020-01-03", bad_price)]))
    with pytest.raises(DataFetchError, match="zero or negative"):
        data_fetcher.fetch_adjusted_prices(["X"], START, END, api_key="k")


def test_very_large_prices_kept_exactly(fake_get):
    fake_get.responses[PRICES_PATH] = FakeResponse(
        payload=_rows("BIG", [("2020-01-02", 1e12)]))
    prices = data_fetcher.fetch_adjusted_prices(["BIG"], START, END, api_key="k")
    assert prices["BIG"].iloc[0] == 1e12


# ---- 10-year Treasury yield ----

def test_yield_uses_most_recent_date_and_converts_to_decimal(fake_get):
    fake_get.responses["treasury-rates"] = FakeResponse(payload=[
        {"date": "2026-11-12", "year10": 5.10},
        {"date": "2026-11-13", "year10": 5.15},
        {"date": "2026-11-10", "year10": 4.90},
    ])
    rate = data_fetcher.fetch_ten_year_yield(api_key="k", today=dt.date(2026, 11, 15))
    assert rate == pytest.approx(0.0515)
    assert fake_get.calls[0]["params"] == {"from": "2026-11-01", "to": "2026-11-15"}


def test_yield_skips_blank_readings(fake_get):
    fake_get.responses["treasury-rates"] = FakeResponse(payload=[
        {"date": "2026-11-13", "year10": None},
        {"date": "2026-11-12", "year10": 5.10},
        "junk",
        {"date": "2026-11-14", "year10": float("nan")},
    ])
    assert data_fetcher.fetch_ten_year_yield(api_key="k") == pytest.approx(0.051)


def test_zero_yield_is_allowed(fake_get):
    fake_get.responses["treasury-rates"] = FakeResponse(
        payload=[{"date": "2026-11-13", "year10": 0}])
    assert data_fetcher.fetch_ten_year_yield(api_key="k") == 0.0


@pytest.mark.parametrize("payload", [[], [{"date": "2026-11-13"}]])
def test_no_yield_found(fake_get, payload):
    fake_get.responses["treasury-rates"] = FakeResponse(payload=payload)
    with pytest.raises(DataFetchError, match="No recent 10-year"):
        data_fetcher.fetch_ten_year_yield(api_key="k")


def test_yield_wrong_format(fake_get):
    fake_get.responses["treasury-rates"] = FakeResponse(payload={"year10": 5})
    with pytest.raises(DataFetchError, match="unexpected format"):
        data_fetcher.fetch_ten_year_yield(api_key="k")
