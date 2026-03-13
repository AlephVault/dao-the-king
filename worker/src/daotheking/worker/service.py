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
from .config import ContractRuntimeConfig, WorkerSettings, iter_requested_events, load_runtime_config, retrieve_sampling
from .etherscan import fetch_transactions_page


LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class WorkerContext:
    """

    """

    settings: WorkerSettings
    storage: MongoDBStorage
    runtime_configs: list[ContractRuntimeConfig]
    contracts: dict[int, dict[str, Any]]


class WorkerService:
    """

    """

    def __init__(self, context: WorkerContext) -> None:
        self._context = context
        self._stop_event = threading.Event()
        self._threads: list[threading.Thread] = []
        self._random = random.Random()

    def run(self) -> int:
        """

        :return:
        """

        self._install_signal_handlers()
        for runtime in self._context.runtime_configs:
            result = self._context.contracts.get(runtime.chain_id, {}).get(runtime.contract.address)
            if result is None or result.contract is None or result.error is not None:
                LOGGER.warning("Skipping %s on chain %s due to load error", runtime.contract.address, runtime.chain_id)
                continue
            self._start_contract_threads(runtime, result.contract)

        if self._context.settings.run_once:
            for thread in self._threads:
                thread.join()
            return 0

        self._stop_event.wait()
        for thread in self._threads:
            thread.join(timeout=2.0)
        return 0

    def stop(self) -> None:
        """

        :return:
        """

        self._stop_event.set()

    def _install_signal_handlers(self) -> None:
        """

        :return:
        """

        def handler(signum: int, _frame: object) -> None:
            LOGGER.info("Received signal %s, stopping worker", signum)
            self.stop()

        signal.signal(signal.SIGINT, handler)
        signal.signal(signal.SIGTERM, handler)

    def _start_contract_threads(self, runtime: ContractRuntimeConfig, contract: Contract) -> None:
        """

        :param runtime:
        :param contract:
        :return:
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
            self._spawn(
                target=self._events_loop,
                name=f"event-{runtime.chain_id}-{runtime.contract.address}-{event_signature}",
                args=(runtime, contract, event_signature, probability, minimum),
            )

    def _spawn(self, *, target: Any, name: str, args: tuple[Any, ...]) -> None:
        """

        :param target:
        :param name:
        :param args:
        :return:
        """

        thread = threading.Thread(target=target, name=name, args=args, daemon=not self._context.settings.run_once)
        thread.start()
        self._threads.append(thread)

    def _transactions_loop(self, runtime: ContractRuntimeConfig, contract: Contract,
                           probability: float | None, minimum: int) -> None:
        """

        :param runtime:
        :param contract:
        :param probability:
        :param minimum:
        :return:
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
                LOGGER.exception("Transactions iteration failed for %s on chain %s", contract.address, runtime.chain_id)
            if self._context.settings.run_once:
                return
            self._stop_event.wait(self._context.settings.poll_interval_seconds)

    def _run_transactions_iteration(self, runtime: ContractRuntimeConfig, contract: Contract,
                                    probability: float | None, minimum: int) -> None:
        """

        :param runtime:
        :param contract:
        :param probability:
        :param minimum:
        :return:
        """

        storage = self._context.storage
        last_block_number, last_transaction_index = storage.get_contract_transactions_bookmark(runtime.chain_id, contract.address)
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

    def _events_loop(self, runtime: ContractRuntimeConfig, contract: Contract, event_signature: str,
                     probability: float | None, minimum: int) -> None:
        """

        :param runtime:
        :param contract:
        :param event_signature:
        :param probability:
        :param minimum:
        :return:
        """

        while not self._stop_event.is_set():
            try:
                self._run_events_iteration(runtime, contract, event_signature, probability, minimum)
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
                              probability: float | None, minimum: int) -> None:
        """

        :param runtime:
        :param contract:
        :param event_signature:
        :param probability:
        :param minimum:
        :return:
        """

        storage = self._context.storage
        last_block_number, last_transaction_index, last_log_index = storage.get_contract_events_bookmark(
            runtime.chain_id,
            contract.address,
            event_signature,
        )
        stored_count = storage.get_events_count(runtime.chain_id, contract.address, event_signature)
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
                if self._should_store_sampled(stored_count, probability, minimum):
                    to_store.append(normalized)
                    stored_count += 1

            if to_store:
                storage.store_events(runtime.chain_id, contract.address, to_store)
            if last_seen > (last_block_number, last_transaction_index, last_log_index):
                storage.set_contract_events_bookmark(
                    runtime.chain_id,
                    contract.address,
                    event_signature,
                    *last_seen,
                )
                last_block_number, last_transaction_index, last_log_index = last_seen
            start_block = end_block + 1

    def _should_store_sampled(self, stored_count: int, probability: float | None, minimum: int) -> bool:
        """

        :param stored_count:
        :param probability:
        :param minimum:
        :return:
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

        :param runtime:
        :param contract:
        :param transaction:
        :return:
        """

        tx_hash = transaction["hash"]
        tx_hash_hex = tx_hash if isinstance(tx_hash, str) else tx_hash.hex()
        block_number = int(transaction["blockNumber"])
        transaction_index = int(transaction["transactionIndex"])
        receipt = contract.w3.eth.get_transaction_receipt(tx_hash_hex)
        decoded_input: dict[str, Any] | None = None
        input_data = transaction.get("input")
        if input_data and input_data != "0x":
            try:
                function_abi, arguments = contract.decode_function_input(input_data)
                decoded_input = {
                    "function_name": function_abi.fn_name,
                    "arguments": dict(arguments),
                }
            except Exception:
                decoded_input = None

        return {
            "chain_id": runtime.chain_id,
            "contract_address": contract.address,
            "hash": tx_hash_hex,
            "block_number": block_number,
            "transaction_index": transaction_index,
            "transaction": _json_safe_dict(transaction),
            "decoded_input": decoded_input,
            "receipt": _json_safe_dict(dict(receipt)),
        }

    @staticmethod
    def _event_abi_for_signature(contract: Contract, event_signature: str) -> dict[str, Any] | None:
        """

        :param contract:
        :param event_signature:
        :return:
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
    def _normalize_event(contract: Contract, event_signature: str,
                         event_abi: dict[str, Any], log: Any) -> dict[str, Any]:
        """

        :param contract:
        :param event_signature:
        :param event_abi:
        :param log:
        :return:
        """

        decoded = get_event_data(contract.w3.codec, event_abi, log)
        return {
            "contract_address": contract.address,
            "event": event_signature,
            "block_number": int(log["blockNumber"]),
            "transaction_index": int(log["transactionIndex"]),
            "log_index": int(log["logIndex"]),
            "transaction_hash": log["transactionHash"].hex(),
            "args": _json_safe_dict(dict(decoded["args"])),
            "log": _json_safe_dict(dict(log)),
        }


def build_worker_context(settings: WorkerSettings) -> WorkerContext:
    """

    :param settings:
    :return:
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

    :param value:
    :return:
    """

    if isinstance(value, dict):
        return {str(key): _json_safe_dict(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe_dict(item) for item in value]
    if isinstance(value, bytes):
        return "0x" + value.hex()
    if hasattr(value, "hex") and callable(value.hex):
        try:
            return value.hex()
        except TypeError:
            return str(value)
    return value
