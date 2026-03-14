from __future__ import annotations
from typing import Any
from daotheking.core.contracts import known_abis


KNOWN_BADGE_METHODS = {
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


def _split_array_suffix(type_name: str) -> tuple[str, str]:
    """
    Split an ABI type into its base type and any trailing array suffix.
    """

    if "[" not in type_name:
        return type_name, ""
    index = type_name.index("[")
    return type_name[:index], type_name[index:]


def format_parameter_type(parameter: dict[str, Any]) -> str:
    """
    Render one ABI parameter type in Solidity-like syntax.
    """

    type_name = str(parameter.get("type", ""))
    base_type, array_suffix = _split_array_suffix(type_name)
    if base_type != "tuple":
        return f"{base_type}{array_suffix}"
    components = parameter.get("components", [])
    rendered = ", ".join(format_parameter_type(item) for item in components if isinstance(item, dict))
    return f"tuple({rendered}){array_suffix}"


def format_parameter_declaration(parameter: dict[str, Any], *, for_event: bool = False) -> str:
    """
    Render one ABI parameter declaration, optionally including `indexed`.
    """

    chunks = [format_parameter_type(parameter)]
    if for_event and parameter.get("indexed", False):
        chunks.append("indexed")
    name = str(parameter.get("name", "")).strip()
    if name:
        chunks.append(name)
    return " ".join(chunks)


def format_function_signature(entry: dict[str, Any]) -> str:
    """
    Render one ABI function entry as a Solidity-style function signature.
    """

    inputs = ", ".join(format_parameter_declaration(item) for item in entry.get("inputs", []))
    signature = f"function {entry.get('name')}({inputs}) external"
    state_mutability = entry.get("stateMutability")
    if state_mutability in {"view", "pure", "payable"}:
        signature = f"{signature} {state_mutability}"
    outputs = entry.get("outputs", [])
    if outputs:
        rendered = ", ".join(format_parameter_declaration(item) for item in outputs)
        signature = f"{signature} returns ({rendered})"
    return signature


def format_topic_signature(entry: dict[str, Any]) -> str:
    """
    Render the canonical event topic signature without parameter names.
    """

    return f"{entry.get('name')}({','.join(format_parameter_type(item) for item in entry.get('inputs', []))})"


def format_event_signature(entry: dict[str, Any]) -> str:
    """
    Render one ABI event entry as a Solidity-style event signature.
    """

    inputs = ", ".join(format_parameter_declaration(item, for_event=True) for item in entry.get("inputs", []))
    return f"event {entry.get('name')}({inputs})"


def function_key(entry: dict[str, Any]) -> str:
    """
    Build the canonical key used to identify one ABI function entry.
    """

    return f"{entry.get('name')}({','.join(format_parameter_type(item) for item in entry.get('inputs', []))})"


def badge_function_keys() -> dict[str, set[str]]:
    """
    Map each known badge to the canonical function keys declared by its ABI.
    """

    result: dict[str, set[str]] = {}
    for badge, abi in KNOWN_BADGE_METHODS.items():
        result[badge] = {
            function_key(entry)
            for entry in abi
            if entry.get("type") == "function"
        }
    return result
