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
    """
    Container for detected contract badges and derived metadata.
    """

    badges: dict[str, dict[str, Any]] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


def _split_array_suffix(type_name: str) -> tuple[str, str]:
    """
    Split an ABI type into its base type and any trailing array suffix.
    """

    if "[" not in type_name:
        return type_name, ""
    index = type_name.index("[")
    return type_name[:index], type_name[index:]


def _format_parameter_type(parameter: dict[str, Any]) -> str:
    """
    Render the Solidity type for an ABI parameter, including tuple components.
    """

    type_name = str(parameter.get("type", ""))
    base_type, array_suffix = _split_array_suffix(type_name)
    if base_type != "tuple":
        return f"{base_type}{array_suffix}"

    components = parameter.get("components", [])
    rendered_components = ", ".join(_format_parameter_declaration(component) for component in components)
    return f"tuple({rendered_components}){array_suffix}"


def _format_parameter_declaration(parameter: dict[str, Any], *, for_event: bool = False) -> str:
    """
    Render one ABI parameter as a Solidity-like declaration string.
    """

    chunks = [_format_parameter_type(parameter)]
    if for_event and parameter.get("indexed", False):
        chunks.append("indexed")
    name = str(parameter.get("name", "")).strip()
    if name:
        chunks.append(name)
    return " ".join(chunks)


def _format_function_signature(entry: ABIElement) -> str:
    """
    Render one ABI function entry as a Solidity-style function signature.
    """

    inputs = ", ".join(
        _format_parameter_declaration(parameter)
        for parameter in entry.get("inputs", [])
    )
    signature = f"function {entry.get('name')}({inputs}) external"
    state_mutability = entry.get("stateMutability")
    if state_mutability in {"view", "pure", "payable"}:
        signature = f"{signature} {state_mutability}"

    outputs = entry.get("outputs", [])
    if outputs:
        rendered_outputs = ", ".join(
            _format_parameter_declaration(parameter)
            for parameter in outputs
        )
        signature = f"{signature} returns ({rendered_outputs})"
    return signature


def _format_event_signature(entry: ABIElement) -> str:
    """
    Render one ABI event entry as a Solidity-style event signature.
    """

    inputs = ", ".join(
        _format_parameter_declaration(parameter, for_event=True)
        for parameter in entry.get("inputs", [])
    )
    return f"event {entry.get('name')}({inputs})"


def _functions_metadata(abi: list[ABIElement]) -> list[tuple[str, ABIElement]]:
    """
    Build the sorted `(signature, ABI entry)` list for all functions in an ABI.
    """

    functions = [
        (_format_function_signature(entry), entry)
        for entry in abi
        if entry.get("type") == "function" and "name" in entry
    ]
    functions.sort(key=lambda item: item[0])
    return functions


def _events_metadata(abi: list[ABIElement]) -> list[tuple[str, ABIElement]]:
    """
    Build the sorted `(signature, ABI entry)` list for all events in an ABI.
    """

    events = [
        (_format_event_signature(entry), entry)
        for entry in abi
        if entry.get("type") == "event" and "name" in entry
    ]
    events.sort(key=lambda item: item[0])
    return events


def _normalize_parameter(parameter: dict[str, Any], *, is_event: bool) -> dict[str, Any]:
    """
    Normalize an ABI parameter for structural comparison, ignoring names.
    """

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
    """
    Normalize a function or event ABI entry into a comparable shape.
    """

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
    """
    Convert an ABI into a set of normalized JSON strings for subset checks.
    """

    result: set[str] = set()
    for entry in abi:
        normalized = _normalize_abi_entry(entry)
        if normalized is not None:
            result.add(json.dumps(normalized, sort_keys=True))
    return result


def _match_known_badges(abi: list[ABIElement]) -> set[str]:
    """
    Return the known badges whose canonical ABI fragments are present in the ABI.
    """

    contract_entries = _normalized_abi_set(abi)
    matched: set[str] = set()
    for badge, badge_abi in KNOWN_BADGE_ABIS.items():
        if _normalized_abi_set(badge_abi).issubset(contract_entries):
            matched.add(badge)
    return matched


def _safe_call(contract: Contract, function_name: str) -> Any | None:
    """
    Call a zero-argument contract function and return `None` on failure.
    """

    functions = getattr(contract, "functions", None)
    if functions is None or not hasattr(functions, function_name):
        return None
    try:
        return getattr(functions, function_name)().call()
    except Exception:
        return None


def _extract_erc1967_slots(contract: Contract) -> dict[str, Any]:
    """
    Read the standard ERC-1967 storage slots and return populated addresses.
    """

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
    """
    Detect supported badges for a contract and collect static metadata about it.
    """

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
        "functions": _functions_metadata(abi),
        "events": _events_metadata(abi),
        "matched_badges": sorted(detected),
    }
    return ContractBadgeResult(badges=badges, metadata=metadata)


METADATA_FROM_KNOWN_BADGE_ABIS = {
    key: {
        "functions": _functions_metadata(abi),
        "events": _events_metadata(abi)
    }
    for key, abi in KNOWN_BADGE_ABIS.items()
}
