from __future__ import annotations
from dataclasses import dataclass
import streamlit as st
from eth_typing import ABIElement
from web3.contract import Contract
from daotheking.core import MongoDBStorage, load_contracts
from daotheking.core.contracts.loader import ContractLoadResult
from .abi import badge_function_keys, function_key
from .settings import ServerSettings


@dataclass(slots=True)
class ServerData:
    """
    Bundle the server-wide resources reused across Streamlit reruns.

    This keeps the loaded contracts, storage backend, and badge-to-method map
    together so page renderers can receive one coherent object instead of
    repeatedly rebuilding the same dependencies.
    """

    settings: ServerSettings
    storage: MongoDBStorage
    contracts: dict[int, dict[str, ContractLoadResult]]
    badge_methods: dict[str, set[str]]


@st.cache_resource(show_spinner=False)
def load_server_data(settings: ServerSettings) -> ServerData:
    """
    Load and cache the shared server resources for the current configuration.

    Streamlit reruns the script on every interaction, so the MongoDB backend and
    contract registry must be cached to avoid reconnecting and recomputing
    badges on every render.
    """

    storage = MongoDBStorage.from_uri(settings.mongodb_uri, settings.mongodb_database)
    contracts, error = load_contracts(
        contracts_file_path=settings.contracts_file_path,
        etherscan_api_key=settings.etherscan_api_key,
        storage=storage,
    )
    if error is not None:
        raise RuntimeError(f"could not load contracts: {error}")
    return ServerData(
        settings=settings,
        storage=storage,
        contracts=contracts,
        badge_methods=badge_function_keys(),
    )


def function_entries(contract: Contract) -> list[ABIElement]:
    """
    Return the contract ABI function entries sorted by their canonical key.

    The rest of the server uses the same key format for routing, filtering, and
    badge matching, so sorting by that key keeps the method list stable.
    """

    entries = [entry for entry in contract.abi if entry.get("type") == "function"]
    # Sort by the canonical `name(type1,type2,...)` form used everywhere else.
    entries.sort(key=function_key)
    return entries
