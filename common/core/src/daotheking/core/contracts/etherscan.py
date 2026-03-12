from __future__ import annotations
import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen


ETHERSCAN_V2_URL = "https://api.etherscan.io/v2/api"


@dataclass(slots=True)
class EtherscanAbiResponse:
    """
    Result of an Etherscan ABI lookup attempt.
    """

    ok: bool
    abi: list[dict[str, Any]] | None = None
    contract_not_verified: bool = False
    error_message: str | None = None


def fetch_abi_from_etherscan(*, api_key: str, chain_id: int, address: str, timeout: float = 15.0)\
        -> EtherscanAbiResponse:
    """
    Fetch a contract ABI from Etherscan V2 for one chain and address.

    The response distinguishes "contract not verified" from other Etherscan or
    transport failures so callers can map the outcome to the expected loader
    error codes.
    """

    params = urlencode(
        {
            "module": "contract",
            "action": "getabi",
            "chainid": str(chain_id),
            "address": address,
            "apikey": api_key,
        }
    )
    url = f"{ETHERSCAN_V2_URL}?{params}"
    try:
        with urlopen(url, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        return EtherscanAbiResponse(ok=False, error_message=str(exc))

    message = str(payload.get("message", ""))
    result = payload.get("result")
    if message == "NOTOK":
        result_text = str(result or "")
        # Etherscan reports multiple failure modes through the same envelope, so
        # the textual result is needed to single out unverified contracts.
        if "not verified" in result_text.lower():
            return EtherscanAbiResponse(ok=False, contract_not_verified=True, error_message=result_text)
        return EtherscanAbiResponse(ok=False, error_message=result_text or "etherscan error")

    try:
        # On success, the ABI itself is encoded as a JSON string in `result`.
        abi = json.loads(result)
    except (TypeError, json.JSONDecodeError) as exc:
        return EtherscanAbiResponse(ok=False, error_message=str(exc))

    if not isinstance(abi, list):
        return EtherscanAbiResponse(ok=False, error_message="etherscan ABI payload is not a list")
    return EtherscanAbiResponse(ok=True, abi=abi)
