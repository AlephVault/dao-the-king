from __future__ import annotations
import logging
import random
import signal
import threading
from dataclasses import dataclass
from typing import Any
from web3 import Web3
from web3._utils.events import get_event_data
from web3.contract import Contract
from daotheking.core import MongoDBStorage, load_contracts
from .config import (ContractRuntimeConfig, WorkerSettings, iter_requested_events,
                     load_runtime_config, retrieve_sampling)
from .etherscan import fetch_transactions_page


LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class WorkerContext:
    """
    Fully prepared runtime state for the worker service.
    """

    settings: WorkerSettings
    storage: MongoDBStorage
    runtime_configs: list[ContractRuntimeConfig]
    contracts: dict[int, dict[str, Any]]


class WorkerService:
    """
    Long-running background worker that polls transactions and logs.
    """

    def __init__(self, context: WorkerContext) -> None:
        """
        Initialize the worker service with its prepared runtime context.
        """

        self._context = context
        self._stop_event = threading.Event()
        self._threads: list[threading.Thread] = []
        self._random = random.Random()

    def run(self) -> int:
        """
        Start the required polling threads and keep the worker alive.
        """

        self._install_signal_handlers()
        for runtime in self._context.runtime_configs:
            result = self._context.contracts.get(runtime.chain_id, {}).get(runtime.contract.address)
            if result is None or result.contract is None or result.error is not None:
                LOGGER.warning("Skipping %s on chain %s due to load error",
                               runtime.contract.address, runtime.chain_id)
                continue
            self._start_contract_threads(runtime, result.contract)

        if not self._threads:
            LOGGER.error("Worker did not start any polling threads")
            return 1

        if self._context.settings.run_once:
            for thread in self._threads:
                thread.join()
            return 0

        while not self._stop_event.wait(1.0):
            if not any(thread.is_alive() for thread in self._threads):
                LOGGER.error("All worker threads stopped unexpectedly")
                return 1
        for thread in self._threads:
            thread.join(timeout=2.0)
        return 0

    def stop(self) -> None:
        """
        Request a graceful stop for the worker service.
        """

        self._stop_event.set()

    def _install_signal_handlers(self) -> None:
        """
        Register process signal handlers that trigger graceful shutdown.
        """

        def handler(signum: int, _frame: object) -> None:
            LOGGER.info("Received signal %s, stopping worker", signum)
            self.stop()

        signal.signal(signal.SIGINT, handler)
        signal.signal(signal.SIGTERM, handler)

    def _start_contract_threads(self, runtime: ContractRuntimeConfig, contract: Contract) -> None:
        """
        Start the transaction and event threads required for one contract.
        """

        enabled, probability, minimum = retrieve_sampling(runtime.contract.retrieve.transactions)
        if enabled:
            self._spawn(
                target=self._transactions_loop,
                name=f"tx-{runtime.chain_id}-{runtime.contract.address}",
                args=(runtime, contract, probability, minimum),
            )

        for event_signature, rule in iter_requested_events(runtime, list(contract.abi)):
            enabled, probability, minimum = retrieve_sampling(rule)
            if not enabled:
                continue
            event_key = self._event_storage_key(event_signature)
            self._spawn(
                target=self._events_loop,
                name=f"event-{runtime.chain_id}-{runtime.contract.address}-{event_key}",
                args=(runtime, contract, event_signature, event_key, probability, minimum),
            )

    def _spawn(self, *, target: Any, name: str, args: tuple[Any, ...]) -> None:
        """
        Spawn one worker thread and keep track of it for shutdown.
        """

        thread = threading.Thread(target=target, name=name, args=args, daemon=not self._context.settings.run_once)
        thread.start()
        self._threads.append(thread)

    def _transactions_loop(self, runtime: ContractRuntimeConfig, contract: Contract,
                           probability: float | None, minimum: int) -> None:
        """
        Continuously poll and store transactions for one contract.
        """

        if not self._context.settings.etherscan_api_key:
            LOGGER.warning(
                "Transactions retrieval requested for %s on chain %s but ETHERSCAN_API_KEY is missing",
                contract.address,
                runtime.chain_id,
            )
            return

        while not self._stop_event.is_set():
            try:
                self._run_transactions_iteration(runtime, contract, probability, minimum)
            except Exception:
                LOGGER.exception("Transactions iteration failed for %s on chain %s",
                                 contract.address, runtime.chain_id)
            if self._context.settings.run_once:
                return
            self._stop_event.wait(self._context.settings.poll_interval_seconds)

    def _run_transactions_iteration(self, runtime: ContractRuntimeConfig, contract: Contract,
                                    probability: float | None, minimum: int) -> None:
        """
        Execute one transaction polling sweep for one contract.
        """

        storage = self._context.storage
        last_block_number, last_transaction_index = storage.get_contract_transactions_bookmark(
            runtime.chain_id, contract.address
        )
        stored_count = storage.get_transactions_count(runtime.chain_id, contract.address)
        start_block = max(last_block_number, 0)
        page = 1

        while not self._stop_event.is_set():
            response = fetch_transactions_page(
                api_key=self._context.settings.etherscan_api_key or "",
                chain_id=runtime.chain_id,
                address=contract.address,
                start_block=start_block,
                page=page,
                offset=self._context.settings.etherscan_page_size,
                timeout=self._context.settings.etherscan_timeout,
            )
            if not response.ok:
                LOGGER.warning(
                    "Failed to fetch transactions for %s on chain %s: %s",
                    contract.address,
                    runtime.chain_id,
                    response.error_message,
                )
                return
            if not response.transactions:
                return

            to_store: list[dict[str, Any]] = []
            last_seen = (last_block_number, last_transaction_index)
            for transaction in response.transactions:
                normalized = self._normalize_transaction(runtime, contract, transaction)
                locator = (normalized["block_number"], normalized["transaction_index"])
                if locator <= (last_block_number, last_transaction_index):
                    continue
                last_seen = locator
                # The bookmark must advance across every seen transaction, even
                # when sampling decides not to persist that record.
                if self._should_store_sampled(stored_count, probability, minimum):
                    to_store.append(normalized)
                    stored_count += 1

            if to_store:
                storage.store_transactions(runtime.chain_id, contract.address, to_store)
            if last_seen > (last_block_number, last_transaction_index):
                storage.set_contract_transactions_bookmark(runtime.chain_id, contract.address, *last_seen)
                last_block_number, last_transaction_index = last_seen

            if len(response.transactions) < self._context.settings.etherscan_page_size:
                return
            page += 1

    def _events_loop(self, runtime: ContractRuntimeConfig, contract: Contract, event_signature: str, event_key: str,
                     probability: float | None, minimum: int) -> None:
        """
        Continuously poll and store one event stream for one contract.
        """

        while not self._stop_event.is_set():
            try:
                self._run_events_iteration(runtime, contract, event_signature, event_key, probability, minimum)
            except Exception:
                LOGGER.exception(
                    "Events iteration failed for %s on chain %s and event %s",
                    contract.address,
                    runtime.chain_id,
                    event_signature,
                )
            if self._context.settings.run_once:
                return
            self._stop_event.wait(self._context.settings.poll_interval_seconds)

    def _run_events_iteration(self, runtime: ContractRuntimeConfig, contract: Contract, event_signature: str,
                              event_key: str,
                              probability: float | None, minimum: int) -> None:
        """
        Execute one event polling sweep for one contract and event signature.
        """

        storage = self._context.storage
        last_block_number, last_transaction_index, last_log_index = storage.get_contract_events_bookmark(
            runtime.chain_id,
            contract.address,
            event_key,
        )
        stored_count = storage.get_events_count(runtime.chain_id, contract.address, event_key)
        event_abi = self._event_abi_for_signature(contract, event_signature)
        if event_abi is None:
            LOGGER.warning("Event %s not found in ABI for %s", event_signature, contract.address)
            return

        topic0 = Web3.keccak(text=event_signature).hex()
        start_block = max(last_block_number, 0)
        latest_block = contract.w3.eth.block_number
        block_step = max(self._context.settings.block_batch_size, 1)

        while start_block <= latest_block and not self._stop_event.is_set():
            end_block = min(start_block + block_step - 1, latest_block)
            logs = contract.w3.eth.get_logs(
                {
                    "address": contract.address,
                    "fromBlock": start_block,
                    "toBlock": end_block,
                    "topics": [topic0],
                }
            )
            to_store: list[dict[str, Any]] = []
            last_seen = (last_block_number, last_transaction_index, last_log_index)
            for log in logs:
                normalized = self._normalize_event(contract, event_signature, event_abi, log)
                locator = (
                    normalized["block_number"],
                    normalized["transaction_index"],
                    normalized["log_index"],
                )
                if locator <= (last_block_number, last_transaction_index, last_log_index):
                    continue
                last_seen = locator
                # The bookmark must also advance across skipped event samples so
                # the worker does not loop over the same logs forever.
                if self._should_store_sampled(stored_count, probability, minimum):
                    to_store.append(normalized)
                    stored_count += 1

            if to_store:
                storage.store_events(runtime.chain_id, contract.address, to_store)
            if last_seen > (last_block_number, last_transaction_index, last_log_index):
                storage.set_contract_events_bookmark(
                    runtime.chain_id,
                    contract.address,
                    event_key,
                    *last_seen,
                )
                last_block_number, last_transaction_index, last_log_index = last_seen
            start_block = end_block + 1

    def _should_store_sampled(self, stored_count: int, probability: float | None, minimum: int) -> bool:
        """
        Decide whether the next record should be persisted under the sampling rule.
        """

        if stored_count < minimum:
            return True
        if probability is None:
            return True
        return self._random.random() < probability

    @staticmethod
    def _normalize_transaction(runtime: ContractRuntimeConfig, contract: Contract,
                               transaction: dict[str, Any]) -> dict[str, Any]:
        """
        Normalize one Etherscan transaction into the worker storage schema.
        """

        tx_hash = transaction["hash"]
        tx_hash_hex = tx_hash if isinstance(tx_hash, str) else tx_hash.hex()
        block_number = int(transaction["blockNumber"])
        transaction_index = int(transaction["transactionIndex"])
        receipt = contract.w3.eth.get_transaction_receipt(tx_hash_hex)
        decoded_input: dict[str, Any] | None = None
        method_selector: str | None = None
        input_data = transaction.get("input")
        if isinstance(input_data, str) and input_data.startswith("0x") and len(input_data) >= 10:
            method_selector = input_data[:10].lower()
        if input_data and input_data != "0x":
            try:
                function_abi, arguments = contract.decode_function_input(input_data)
                canonical_signature = WorkerService._function_signature(function_abi.abi)
                method_selector = WorkerService._function_selector(canonical_signature)
                decoded_input = _json_safe_dict({
                    "function_name": function_abi.fn_name,
                    "function_signature": canonical_signature,
                    "method_selector": method_selector,
                    "arguments": dict(arguments),
                })
            except Exception:
                decoded_input = None

        result = _json_safe_dict(dict(receipt))

        return {
            "chain_id": runtime.chain_id,
            "contract_address": contract.address,
            "hash": tx_hash_hex,
            "block_number": block_number,
            "transaction_index": transaction_index,
            "method_selector": method_selector,
            "transaction": _json_safe_dict(transaction),
            "decoded_input": decoded_input,
            "result": result,
            "receipt": result,
        }

    @staticmethod
    def _function_signature(function_abi: dict[str, Any]) -> str:
        """
        Build the canonical function signature for one ABI function entry.
        """

        return f"{function_abi.get('name')}({','.join(
            WorkerService._abi_parameter_type(item)
            for item in function_abi.get('inputs', [])
            if isinstance(item, dict)
        )})"

    @staticmethod
    def _function_selector(function_signature: str) -> str:
        """
        Convert a canonical function signature into its 4-byte selector hex string.
        """

        return "0x" + Web3.keccak(text=function_signature).hex()[:8]

    @staticmethod
    def _abi_parameter_type(parameter: dict[str, Any]) -> str:
        """
        Render one ABI parameter into the canonical type-only signature form.
        """

        type_name = str(parameter.get("type", ""))
        if not type_name.startswith("tuple"):
            return type_name

        array_suffix = type_name[5:]
        components = ",".join(
            WorkerService._abi_parameter_type(item)
            for item in parameter.get("components", [])
            if isinstance(item, dict)
        )
        return f"tuple({components}){array_suffix}"

    @staticmethod
    def _event_abi_for_signature(contract: Contract, event_signature: str) -> dict[str, Any] | None:
        """
        Find the ABI entry for one canonical event topic signature.
        """

        for entry in contract.abi:
            if entry.get("type") != "event":
                continue
            candidate = f"{entry.get('name')}({','.join(
                str(item.get('type'))
                for item in entry.get('inputs', [])
            )})"
            if candidate == event_signature:
                return dict(entry)
        return None

    @staticmethod
    def _event_storage_key(event_signature: str) -> str:
        """
        Convert an event signature into the keccak hash used as the storage key.
        """

        return "0x" + Web3.keccak(text=event_signature).hex()

    @staticmethod
    def _normalize_event(contract: Contract, event_signature: str,
                         event_abi: dict[str, Any], log: Any) -> dict[str, Any]:
        """
        Normalize one RPC log into the worker storage schema.
        """

        decoded = get_event_data(contract.w3.codec, event_abi, log)
        event_hash = WorkerService._event_storage_key(event_signature)
        return {
            "contract_address": contract.address,
            "event": event_hash,
            "event_signature": event_signature,
            "event_hash": event_hash,
            "block_number": int(log["blockNumber"]),
            "transaction_index": int(log["transactionIndex"]),
            "log_index": int(log["logIndex"]),
            "transaction_hash": log["transactionHash"].hex(),
            "args": _json_safe_dict(dict(decoded["args"])),
            "log": _json_safe_dict(dict(log)),
        }


def build_worker_context(settings: WorkerSettings) -> WorkerContext:
    """
    Resolve the worker configuration, storage backend, and loaded contracts.
    """

    storage = MongoDBStorage.from_uri(settings.mongodb_uri, settings.mongodb_database)
    runtime_configs = load_runtime_config(settings.contracts_file_path)
    contracts, error = load_contracts(
        contracts_file_path=settings.contracts_file_path,
        etherscan_api_key=settings.etherscan_api_key,
        storage=storage,
    )
    if error is not None:
        raise RuntimeError(f"failed to load contracts file: {error}")
    return WorkerContext(settings=settings, storage=storage, runtime_configs=runtime_configs, contracts=contracts)


def _json_safe_dict(value: Any) -> Any:
    """
    Convert nested Web3 values into JSON-safe Python primitives.
    """

    if isinstance(value, dict):
        return {str(key): _json_safe_dict(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe_dict(item) for item in value]
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return str(value)
    if isinstance(value, bytes):
        return "0x" + value.hex()
    if hasattr(value, "hex") and callable(value.hex):
        try:
            return value.hex()
        except TypeError:
            return str(value)
    return value
