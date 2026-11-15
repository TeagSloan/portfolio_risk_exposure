"""Contract interfaces (ABIs) for the Phase 7 contracts: just the functions the Python side calls.

Written out by hand so the Python code works without running `forge build` first. If a contract's
function changes in contracts/src/, change it here too (tests/test_publish.py checks they still match
when the compiled contracts are available).
"""

_EXPOSURE = {
    "type": "tuple",
    "components": [
        {"name": "tier", "type": "uint8"},
        {"name": "baselineHash", "type": "bytes32"},
        {"name": "statsHash", "type": "bytes32"},
        {"name": "timestamp", "type": "uint256"},
    ],
}


def _fn(name: str, inputs: list[tuple[str, str]], outputs: list, mutability: str = "view") -> dict:
    return {
        "type": "function",
        "name": name,
        "stateMutability": mutability,
        "inputs": [{"name": n, "type": t} for n, t in inputs],
        "outputs": [o if isinstance(o, dict) else {"name": "", "type": o} for o in outputs],
    }


FACTORY_ABI = [
    _fn("exchange", [], ["address"]),
    _fn("allFunds", [], ["address[]"]),
]

EXCHANGE_ABI = [
    _fn("oracle", [], ["address"]),
    _fn("usdc", [], ["address"]),
    _fn("owner", [], ["address"]),
    _fn("stockOf", [("ticker", "bytes32")], ["address"]),
    _fn("allStocks", [], ["address[]"]),
    _fn("listStock", [("name", "string"), ("symbol", "string")], ["address"], "nonpayable"),
]

ORACLE_ABI = [
    _fn("owner", [], ["address"]),
    _fn("priceOf", [("ticker", "bytes32")], ["uint256", "uint256"]),
    _fn("tierOf", [("ticker", "bytes32"), ("theme", "bytes32")], ["uint8"]),
    _fn("exposureOf", [("ticker", "bytes32"), ("theme", "bytes32")], [_EXPOSURE]),
    _fn("postPrices", [("tickers", "bytes32[]"), ("prices", "uint256[]")], [], "nonpayable"),
    _fn(
        "postExposures",
        [
            ("tickers", "bytes32[]"),
            ("themes", "bytes32[]"),
            ("tiers", "uint8[]"),
            ("baselineHashes", "bytes32[]"),
            ("statsHashes", "bytes32[]"),
        ],
        [],
        "nonpayable",
    ),
]
