"""Fixtures for the mean-variance tests."""

import pytest
from price_simulator import make_prices


@pytest.fixture
def prices_three():
    return make_prices(["AAA", "BBB", "CCC"])


@pytest.fixture
def prices_with_ipo():
    return make_prices(["AAA", "BBB", "NEW"], start_after={"NEW": "2023-06-01"}, seed=1)
