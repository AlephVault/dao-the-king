from __future__ import annotations
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from pydantic import ValidationError
from web3 import HTTPProvider, Web3
from web3.contract import Contract
from .abi import AbiFileCache
from .badges import ContractBadgeResult, detect_contract_badges
from .etherscan import fetch_abi_from_etherscan
from .models import ChainEntry, ContractLoadError, ContractsFile
from ..storage import StorageBackend


@dataclass(slots=True)
class ContractLoadResult:
    """
    Outcome of loading one configured contract for one chain.
    """

    contract: Contract | None
    error: ContractLoadError | None = None
    badges: ContractBadgeResult | None = None
    abi_source: str | None = None
    warnings: list[str] = field(default_factory=list)


def _validate_abi_payload(abi: list[dict[str, Any]]) -> None:
    """
    Validate that a decoded ABI payload has the minimal list-of-objects shape.
    """

    for index, entry in enumerate(abi):
        if not isinstance(entry, dict):
            raise ValueError(f"ABI entry at index {index} must be an object")
        if "type" not in entry:
            raise ValueError(f"ABI entry at index {index} must define a type")


def _read_contracts_file(path: str | None) -> ContractsFile:
    """
    Open and validate the contracts configuration file.
    """

    if not path or not path.endswith(".json"):
        raise OSError("invalid path")
    target = Path(path)
    with target.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return ContractsFile.model_validate(payload)


def _build_web3(chain: ChainEntry) -> Web3:
    """
    Create the Web3 client for one configured chain.
    """

    return Web3(HTTPProvider(str(chain.rpc)))


def _load_abi_for_contract(
    *,
    abi_file_cache: AbiFileCache,
    chain_id: int,
    address: str,
    abi_path: str | None,
    api_key: str | None,
) -> tuple[list[dict[str, Any]] | None, str | None, ContractLoadError | None, list[str]]:
    """
    Resolve a contract ABI from file first and then from Etherscan if needed.

    The returned error follows the loader contract: invalid local ABI files only
    become terminal if a usable ABI cannot be obtained from Etherscan.
    """

    warnings: list[str] = []
    if abi_path:
        try:
            abi = abi_file_cache.load(abi_path)
            _validate_abi_payload(abi)
            return abi, "file", None, warnings
        except Exception as exc:
            # A broken local ABI file downgrades to a warning first because the
            # contract may still be verified and recoverable through Etherscan.
            warnings.append(f"failed to load ABI file {abi_path}: {exc}")

    if api_key is None:
        return None, None, ContractLoadError.NO_API_KEY_FOR_VERIFICATION, warnings

    response = fetch_abi_from_etherscan(api_key=api_key, chain_id=chain_id, address=address)
    if response.ok:
        try:
            assert response.abi is not None
            _validate_abi_payload(response.abi)
            return response.abi, "etherscan", None, warnings
        except Exception as exc:
            warnings.append(f"failed to validate ABI from etherscan for {address}: {exc}")
            return None, "etherscan", ContractLoadError.ETHERSCAN_VERIFICATION_ERROR, warnings
    if response.contract_not_verified:
        return None, None, ContractLoadError.CONTRACT_NOT_VERIFIED, warnings
    return None, None, ContractLoadError.ETHERSCAN_VERIFICATION_ERROR, warnings


def load_contracts(
    *,
    contracts_file_path: str | None,
    etherscan_api_key: str | None = None,
    storage: StorageBackend | None = None,
) -> tuple[dict[int, dict[str, ContractLoadResult]], ContractLoadError | None]:
    """
    Load all configured contracts and return them indexed by chain and address.

    File-level failures return a top-level error together with an empty result.
    Per-contract failures are captured inside `ContractLoadResult`.
    """

    try:
        contracts_file = _read_contracts_file(contracts_file_path)
    except OSError:
        return {}, ContractLoadError.COULD_NOT_OPEN_CONTRACTS_FILE
    except (json.JSONDecodeError, ValidationError, ValueError):
        return {}, ContractLoadError.INVALID_CONTRACTS_FILE_FORMAT

    results: dict[int, dict[str, ContractLoadResult]] = {}
    abi_file_cache = AbiFileCache()

    for chain_id, chain in contracts_file.chains.items():
        web3 = _build_web3(chain)
        chain_results: dict[str, ContractLoadResult] = {}
        for entry in chain.contracts:
            if not Web3.is_checksum_address(entry.address):
                chain_results[entry.address] = ContractLoadResult(contract=None, error=ContractLoadError.INVALID_ADDRESS)
                continue

            abi, abi_source, error, warnings = _load_abi_for_contract(
                abi_file_cache=abi_file_cache,
                chain_id=chain_id,
                address=entry.address,
                abi_path=entry.abi,
                api_key=etherscan_api_key,
            )
            if abi is None:
                chain_results[entry.address] = ContractLoadResult(
                    contract=None,
                    error=error or ContractLoadError.INVALID_ABI_FILE,
                    abi_source=abi_source,
                    warnings=warnings,
                )
                continue

            try:
                contract = web3.eth.contract(address=entry.address, abi=abi)
            except Exception as exc:
                # Web3 contract construction is the final ABI sanity check.
                warnings.append(f"failed to instantiate contract for {entry.address}: {exc}")
                chain_results[entry.address] = ContractLoadResult(
                    contract=None,
                    error=ContractLoadError.INVALID_ABI_FILE,
                    abi_source=abi_source,
                    warnings=warnings,
                )
                continue
            badges = None
            if storage is not None:
                cached = storage.get_contract_cache(chain_id, entry.address)
                if cached is not None:
                    badges = ContractBadgeResult(
                        badges=dict(cached.get("badges", {})),
                        metadata=dict(cached.get("metadata", {})),
                    )
            if badges is None:
                badges = detect_contract_badges(contract)
                if storage is not None:
                    storage.set_contract_cache(
                        chain_id,
                        entry.address,
                        {"badges": badges.badges, "metadata": badges.metadata},
                    )

            chain_results[entry.address] = ContractLoadResult(
                contract=contract,
                badges=badges,
                abi_source=abi_source,
                warnings=warnings,
            )
        results[chain_id] = chain_results
    return results, None


def load_contracts_from_env(*, storage: StorageBackend | None = None) -> tuple[dict[int, dict[str, ContractLoadResult]], ContractLoadError | None]:
    """
    Load contracts using `DTK_CONTRACTS_FILE` and `ETHERSCAN_API_KEY`.
    """

    return load_contracts(
        contracts_file_path=os.getenv("DTK_CONTRACTS_FILE"),
        etherscan_api_key=os.getenv("ETHERSCAN_API_KEY"),
        storage=storage,
    )
