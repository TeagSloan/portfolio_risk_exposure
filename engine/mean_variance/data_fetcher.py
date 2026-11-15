"""Pulls data from Financial Modeling Prep (FMP).

Two things come from FMP:
1. Daily closing prices adjusted for dividends and splits, so returns include
   dividends paid, not just price changes.
2. The current 10-year Treasury yield, used as the risk-free rate.

The API key is read from the FMP_API_KEY environment variable and sent in a
request header, so it never appears in a URL or in the code.
"""

import datetime as dt
import math
import os

import pandas as pd
import requests

from .errors import DataFetchError

BASE_URL = "https://financialmodelingprep.com/stable"
REQUEST_TIMEOUT_SECONDS = 30
# How far back to look for the latest Treasury reading (covers long weekends).
TREASURY_LOOKBACK_DAYS = 14


def get_api_key(api_key=None):
    """Return the API key passed in, or the one in the FMP_API_KEY setting."""
    key = api_key or os.environ.get("FMP_API_KEY", "")
    key = key.strip()
    if not key:
        raise DataFetchError(
            "No FMP API key found. Set the FMP_API_KEY environment variable "
            "or pass api_key=... to the tool."
        )
    return key


def _get_json(path, params, api_key):
    """Call one FMP endpoint and return the parsed JSON, or raise a clear error."""
    url = f"{BASE_URL}/{path}"
    try:
        response = requests.get(
            url,
            params=params,
            headers={"apikey": api_key},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        raise DataFetchError(f"Could not reach FMP ({exc.__class__.__name__}).") from exc

    if response.status_code in (401, 403):
        raise DataFetchError(
            "FMP rejected the API key, or your plan does not include this data."
        )
    if response.status_code == 429:
        raise DataFetchError("FMP rate limit reached. Wait a minute and try again.")
    if response.status_code != 200:
        raise DataFetchError(f"FMP returned an error (HTTP {response.status_code}).")

    try:
        data = response.json()
    except ValueError as exc:
        raise DataFetchError("FMP sent back data that could not be read.") from exc

    if isinstance(data, dict) and "Error Message" in data:
        raise DataFetchError(f"FMP error: {data['Error Message']}")
    return data


def fetch_adjusted_prices(tickers, start, end, api_key=None):
    """Daily dividend-adjusted closing prices, one column per ticker.

    Dates where a stock did not trade yet (e.g. before its IPO) are left blank,
    so the next step can see how much history each stock really has.
    """
    key = get_api_key(api_key)
    columns = {}
    for ticker in tickers:
        rows = _get_json(
            "historical-price-eod/dividend-adjusted",
            {"symbol": ticker, "from": start.isoformat(), "to": end.isoformat()},
            key,
        )
        if not isinstance(rows, list) or not rows:
            raise DataFetchError(
                f"No price data found for '{ticker}'. Check the ticker symbol."
            )
        try:
            series = pd.Series(
                {pd.Timestamp(row["date"]): float(row["adjClose"]) for row in rows}
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise DataFetchError(
                f"Price data for '{ticker}' was missing dates or prices."
            ) from exc
        if (series <= 0).any():
            raise DataFetchError(f"Price data for '{ticker}' contains zero or negative prices.")
        columns[ticker] = series.sort_index()

    return pd.DataFrame(columns).sort_index()


def fetch_ten_year_yield(api_key=None, today=None):
    """Latest 10-year Treasury yield as a decimal (5.15% is returned as 0.0515)."""
    key = get_api_key(api_key)
    today = today or dt.date.today()
    rows = _get_json(
        "treasury-rates",
        {
            "from": (today - dt.timedelta(days=TREASURY_LOOKBACK_DAYS)).isoformat(),
            "to": today.isoformat(),
        },
        key,
    )
    if not isinstance(rows, list):
        raise DataFetchError("FMP sent back Treasury data in an unexpected format.")

    readings = []
    for row in rows:
        value = row.get("year10") if isinstance(row, dict) else None
        if isinstance(value, (int, float)) and math.isfinite(value) and "date" in row:
            readings.append((row["date"], float(value)))
    if not readings:
        raise DataFetchError("No recent 10-year Treasury yield found on FMP.")

    _, latest_percent = max(readings)  # most recent date wins
    return latest_percent / 100.0
