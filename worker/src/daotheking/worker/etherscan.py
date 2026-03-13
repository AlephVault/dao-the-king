from __future__ import annotations
import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen


ETHERSCAN_V2_URL = "https://api.etherscan.io/v2/api"


@dataclass(slots=True)
class EtherscanTransactionsResponse:
    """

    """

    ok: bool
    transactions: list[dict[str, Any]]
    error_message: str | None = None


def fetch_transactions_page(
    *,
    api_key: str,
    chain_id: int,
    address: str,
    start_block: int,
    page: int,
    offset: int,
    timeout: float,
) -> EtherscanTransactionsResponse:
    """

    :param api_key:
    :param chain_id:
    :param address:
    :param start_block:
    :param page:
    :param offset:
    :param timeout:
    :return:
    """

    params = urlencode(
        {
            "module": "account",
            "action": "txlist",
            "chainid": str(chain_id),
            "address": address,
            "startblock": str(start_block),
            "endblock": "99999999",
            "page": str(page),
            "offset": str(offset),
            "sort": "asc",
            "apikey": api_key,
        }
    )
    try:
        with urlopen(f"{ETHERSCAN_V2_URL}?{params}", timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        return EtherscanTransactionsResponse(ok=False, transactions=[], error_message=str(exc))

    message = str(payload.get("message", ""))
    result = payload.get("result")
    if message == "NOTOK":
        result_text = str(result or "")
        if "no transactions found" in result_text.lower():
            return EtherscanTransactionsResponse(ok=True, transactions=[])
        return EtherscanTransactionsResponse(ok=False, transactions=[], error_message=result_text or "etherscan error")

    if not isinstance(result, list):
        return EtherscanTransactionsResponse(ok=False, transactions=[], error_message="etherscan tx payload is not a list")
    return EtherscanTransactionsResponse(ok=True, transactions=result)
