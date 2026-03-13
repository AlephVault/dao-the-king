from __future__ import annotations
import json
import os
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from daotheking.core.contracts.models import ChainEntry, ContractEntry, ContractsFile, RetrievalSampling


LOGGER = logging.getLogger(__name__)


def _env_flag(name: str, default: bool = False) -> bool:
    """
    Read a boolean flag from the environment using common truthy values.
    """

    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(slots=True)
class WorkerSettings:
    """
    Environment-driven runtime configuration for the worker process.
    """

    mongodb_uri: str
    mongodb_database: str
    etherscan_api_key: str | None
    contracts_file_path: str
    poll_interval_seconds: float = 15.0
    block_batch_size: int = 2_000
    etherscan_page_size: int = 100
    etherscan_timeout: float = 15.0
    run_once: bool = False

    @classmethod
    def from_env(cls) -> "WorkerSettings":
        """
        Build worker settings from environment variables.
        """

        contracts_file_path = os.getenv("DTK_CONTRACTS_FILE")
        mongodb_uri = os.getenv("DTK_MONGODB_URI")
        mongodb_database = os.getenv("DTK_MONGODB_DATABASE", "daotheking")

        if not contracts_file_path:
            raise ValueError("DTK_CONTRACTS_FILE is required")
        if not mongodb_uri:
            raise ValueError("DTK_MONGODB_URI is required")

        return cls(
            mongodb_uri=mongodb_uri,
            mongodb_database=mongodb_database,
            etherscan_api_key=os.getenv("ETHERSCAN_API_KEY"),
            contracts_file_path=contracts_file_path,
            poll_interval_seconds=float(os.getenv("DTK_WORKER_POLL_INTERVAL", "15")),
            block_batch_size=int(os.getenv("DTK_WORKER_BLOCK_BATCH_SIZE", "2000")),
            etherscan_page_size=int(os.getenv("DTK_WORKER_ETHERSCAN_PAGE_SIZE", "100")),
            etherscan_timeout=float(os.getenv("DTK_WORKER_ETHERSCAN_TIMEOUT", "15")),
            run_once=_env_flag("DTK_WORKER_ONCE", default=False),
        )


@dataclass(slots=True)
class ContractRuntimeConfig:
    """
    One configured contract together with the chain it belongs to.
    """

    chain_id: int
    chain: ChainEntry
    contract: ContractEntry


def load_runtime_config(path: str) -> list[ContractRuntimeConfig]:
    """
    Parse the contracts file and flatten it into per-contract runtime entries.
    """

    target = Path(path)
    with target.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    contracts_file = ContractsFile.model_validate(payload)
    result: list[ContractRuntimeConfig] = []
    for chain_id, chain in contracts_file.chains.items():
        for contract in chain.contracts:
            result.append(ContractRuntimeConfig(chain_id=chain_id, chain=chain, contract=contract))
    return result


def retrieve_sampling(rule: bool | RetrievalSampling) -> tuple[bool, float | None, int]:
    """
    Convert a retrieval rule into `(enabled, probability, minimum)`.
    """

    if rule is False:
        return False, None, 0
    if rule is True:
        return True, None, 0
    return True, float(rule.probability), int(rule.min)


def iter_requested_events(runtime: ContractRuntimeConfig, contract_abi: list[dict[str, object]])\
        -> Iterable[tuple[str, bool | RetrievalSampling]]:
    """
    Resolve the configured event selection into canonical topic signatures.
    """

    events_rule = runtime.contract.retrieve.events
    event_entries = [entry for entry in contract_abi if entry.get("type") == "event" and "name" in entry]
    if events_rule is False:
        return []
    if events_rule is True:
        return [(format_event_topic_signature(entry), True) for entry in event_entries]

    resolved: list[tuple[str, bool | RetrievalSampling]] = []
    seen_signatures: set[str] = set()
    for requested_name, rule in events_rule.items():
        matches = [
            entry
            for entry in event_entries
            if event_matches_request(entry, requested_name)
        ]
        if not matches:
            LOGGER.warning("Configured event selector %s did not match any ABI event", requested_name)
        for entry in matches:
            signature = format_event_topic_signature(entry)
            if signature in seen_signatures:
                continue
            seen_signatures.add(signature)
            resolved.append((signature, rule))
    return resolved


def _split_array_suffix(type_name: str) -> tuple[str, str]:
    """
    Split an ABI type into its base type and any array suffix.
    """

    if "[" not in type_name:
        return type_name, ""
    index = type_name.index("[")
    return type_name[:index], type_name[index:]


def format_abi_type(parameter: dict[str, object]) -> str:
    """
    Render one ABI parameter type in canonical Solidity form.
    """

    type_name = str(parameter.get("type", ""))
    base_type, array_suffix = _split_array_suffix(type_name)
    if base_type != "tuple":
        return f"{base_type}{array_suffix}"
    components = parameter.get("components", [])
    if not isinstance(components, list):
        components = []
    rendered = ",".join(format_abi_type(component) for component in components if isinstance(component, dict))
    return f"({rendered}){array_suffix}"


def format_event_signature(entry: dict[str, object], *, include_names: bool = True) -> str:
    """
    Render an event signature, optionally including parameter names.
    """

    rendered_inputs: list[str] = []
    for parameter in entry.get("inputs", []):
        if not isinstance(parameter, dict):
            continue
        chunks = [format_abi_type(parameter)]
        if parameter.get("indexed", False):
            chunks.append("indexed")
        if include_names:
            name = str(parameter.get("name", "")).strip()
            if name:
                chunks.append(name)
        rendered_inputs.append(" ".join(chunks))
    return f"{entry.get('name')}({', '.join(rendered_inputs)})"


def format_event_topic_signature(entry: dict[str, object]) -> str:
    """
    Render the canonical event topic signature used for keccak matching.
    """

    rendered_inputs = []
    for parameter in entry.get("inputs", []):
        if isinstance(parameter, dict):
            rendered_inputs.append(format_abi_type(parameter))
    return f"{entry.get('name')}({','.join(rendered_inputs)})"


def event_matches_request(entry: dict[str, object], requested_name: str) -> bool:
    """
    Check whether one configured selector matches one ABI event entry.
    """

    simple_name = str(entry.get("name", ""))
    if requested_name == simple_name:
        return True
    requested = requested_name.replace("event ", "").strip()
    return requested in {
        format_event_signature(entry, include_names=True),
        format_event_signature(entry, include_names=False),
        format_event_topic_signature(entry),
    }
