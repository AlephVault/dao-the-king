from __future__ import annotations
import json
from dataclasses import dataclass, field
from typing import Any

from eth_typing import ABIElement
from web3.contract import Contract
from . import known_abis

ERC1967_SLOTS = {
    "implementation": "0x360894A13BA1A3210667C828492DB98DCA3E2076CC3735A920A3CA505D382BBC",
    "admin": "0xB53127684A568B3173AE13B9F8A6016E243E63B6E8EE1178D6A717850B5D6103",
    "beacon": "0xA3F0AD74E5423AEBFD80D3EF4346578335A9A72AEAEE59FF6CB3582B35133D50",
}

KNOWN_BADGE_ABIS = {
    "ERC20": known_abis.ERC20,
    "ERC20Metadata": known_abis.ERC20Metadata,
    "ERC165": known_abis.ERC165,
    "ERC721": known_abis.ERC721,
    "ERC721Metadata": known_abis.ERC721Metadata,
    "ERC721TokenReceiver": known_abis.ERC721Receiver,
    "ERC1155": known_abis.ERC1155,
    "ERC1155Metadata_URI": known_abis.ERC1155MetadataURI,
    "ERC1155TokenReceiver": known_abis.ERC1155Receiver,
    "ERC2612": known_abis.ERC2612,
    "ERC3009": known_abis.ERC3009,
    "ERC4337": known_abis.ERC4337,
    "ERC4337Execute": known_abis.ERC4337Execute,
}


@dataclass(slots=True)
class ContractBadgeResult:
    badges: dict[str, dict[str, Any]] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


def _function_names(abi: list[ABIElement]) -> set[str]:
    return {entry["name"] for entry in abi if entry.get("type") == "function" and "name" in entry}


def _event_names(abi: list[ABIElement]) -> set[str]:
    return {entry["name"] for entry in abi if entry.get("type") == "event" and "name" in entry}


def _normalize_parameter(parameter: dict[str, Any], *, is_event: bool) -> dict[str, Any]:
    normalized: dict[str, Any] = {
        "type": parameter.get("type"),
    }
    if is_event:
        normalized["indexed"] = bool(parameter.get("indexed", False))

    if "components" in parameter:
        normalized["components"] = [
            _normalize_parameter(component, is_event=is_event)
            for component in parameter.get("components", [])
        ]
    return normalized


def _normalize_abi_entry(entry: ABIElement) -> dict[str, Any] | None:
    entry_type = entry.get("type")
    if entry_type not in {"function", "event"}:
        return None

    normalized: dict[str, Any] = {
        "type": entry_type,
        "name": entry.get("name"),
        "inputs": [
            _normalize_parameter(item, is_event=entry_type == "event")
            for item in entry.get("inputs", [])
        ],
    }
    if entry_type == "function":
        normalized["outputs"] = [
            _normalize_parameter(item, is_event=False)
            for item in entry.get("outputs", [])
        ]
        normalized["stateMutability"] = entry.get("stateMutability")
    if entry_type == "event":
        normalized["anonymous"] = bool(entry.get("anonymous", False))
    return normalized


def _normalized_abi_set(abi: list[ABIElement]) -> set[str]:
    result: set[str] = set()
    for entry in abi:
        normalized = _normalize_abi_entry(entry)
        if normalized is not None:
            result.add(json.dumps(normalized, sort_keys=True))
    return result


def _match_known_badges(abi: list[ABIElement]) -> set[str]:
    contract_entries = _normalized_abi_set(abi)
    matched: set[str] = set()
    for badge, badge_abi in KNOWN_BADGE_ABIS.items():
        if _normalized_abi_set(badge_abi).issubset(contract_entries):
            matched.add(badge)
    return matched


def _safe_call(contract: Contract, function_name: str) -> Any | None:
    functions = getattr(contract, "functions", None)
    if functions is None or not hasattr(functions, function_name):
        return None
    try:
        return getattr(functions, function_name)().call()
    except Exception:
        return None


def _extract_erc1967_slots(contract: Contract) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for label, slot in ERC1967_SLOTS.items():
        try:
            raw = contract.w3.eth.get_storage_at(contract.address, slot)
        except Exception:
            continue
        if raw and any(raw):
            result[label] = "0x" + raw[-20:].hex()
    return result


def detect_contract_badges(contract: Contract) -> ContractBadgeResult:
    abi: list[ABIElement] = list(contract.abi)
    detected = _match_known_badges(abi)
    badges: dict[str, dict[str, Any]] = {}

    def _add_if_absent(key, value = None):
        if key in detected:
            badges[key] = (value or (lambda: {}))()

    # General
    _add_if_absent("ERC165")

    # ERC-20
    _add_if_absent("ERC20")
    _add_if_absent("ERC20Metadata", lambda: {
        "name": _safe_call(contract, "name"),
        "symbol": _safe_call(contract, "symbol"),
        "decimals": _safe_call(contract, "decimals"),
    })
    _add_if_absent("ERC2612", lambda: {
        "domain_separator": _safe_call(contract, "DOMAIN_SEPARATOR"),
    })
    _add_if_absent("ERC3009", {})

    # ERC-721
    _add_if_absent("ERC721")
    _add_if_absent("ERC721Metadata", lambda: {
        "name": _safe_call(contract, "name"),
        "symbol": _safe_call(contract, "symbol"),
    })

    # ERC-721 Receiver
    _add_if_absent("ERC721TokenReceiver")

    # ERC-1155
    _add_if_absent("ERC1155")
    _add_if_absent("ERC1155Metadata_URI")
    _add_if_absent("ERC1155TokenReceiver")

    # ERC-4337
    _add_if_absent("ERC4337")
    _add_if_absent("ERC4337Execute")

    # ERC-1967
    erc1967 = _extract_erc1967_slots(contract)
    if erc1967:
        badges["ERC1967"] = erc1967

    metadata = {
        "function_names": sorted(_function_names(abi)),
        "event_names": sorted(_event_names(abi)),
        "matched_badges": sorted(detected),
    }
    return ContractBadgeResult(badges=badges, metadata=metadata)
