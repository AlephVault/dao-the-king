from __future__ import annotations
from collections import defaultdict
from typing import Any
from .base import StorageBackend


class InMemoryStorage(StorageBackend):
    """
    Ephemeral in-process storage backend for local development and tests.
    """

    def __init__(self) -> None:
        """
        Initialize empty in-memory collections for all storage concerns.
        """

        self._contract_cache: dict[tuple[int, str], dict[str, Any]] = {}
        self._tx_bookmarks: dict[tuple[int, str], tuple[int, int]] = {}
        self._event_bookmarks: dict[tuple[int, str, str], tuple[int, int, int]] = {}
        self._transactions: dict[tuple[int, str], dict[str, dict[str, Any]]] = defaultdict(dict)
        self._events: dict[tuple[int, str, str], dict[tuple[int, int, int], dict[str, Any]]] = defaultdict(dict)

    def get_contract_cache(self, chain_id: int, contract_address: str) -> dict[str, Any] | None:
        """
        Return the cached badge payload for a contract, if present.
        """

        return self._contract_cache.get((chain_id, contract_address))

    def set_contract_cache(self, chain_id: int, contract_address: str, cache_object: dict[str, Any]) -> None:
        """
        Store the cached badge payload for a contract.
        """

        self._contract_cache[(chain_id, contract_address)] = cache_object

    def clear_contract_cache(self, chain_id: int, contract_address: str) -> None:
        """
        Delete the cache entry for a single contract.
        """

        self._contract_cache.pop((chain_id, contract_address), None)

    def clear_chain_contract_cache(self, chain_id: int) -> None:
        """
        Delete every cache entry associated with one chain.
        """

        keys = [key for key in self._contract_cache if key[0] == chain_id]
        for key in keys:
            self._contract_cache.pop(key, None)

    def clear_all_contracts_cache(self) -> None:
        """
        Delete every cached contract badge payload.
        """

        self._contract_cache.clear()

    def get_contract_transactions_bookmark(self, chain_id: int, contract_address: str) -> tuple[int, int]:
        """
        Return the transaction bookmark for a contract, or `(-1, -1)`.
        """

        return self._tx_bookmarks.get((chain_id, contract_address), (-1, -1))

    def set_contract_transactions_bookmark(self, chain_id: int, contract_address: str, last_block_number: int,
                                           last_transaction_index: int) -> None:
        """
        Store the transaction bookmark for a contract.
        """

        self._tx_bookmarks[(chain_id, contract_address)] = (last_block_number, last_transaction_index)

    def store_transactions(self, chain_id: int, contract_address: str, transactions: list[dict[str, Any]]) -> None:
        """
        Upsert transactions in memory using the transaction hash as key.
        """

        target = self._transactions[(chain_id, contract_address)]
        for transaction in transactions:
            tx_hash = str(transaction["hash"])
            target[tx_hash] = transaction

    def get_transactions(self, chain_id: int, contract_address: str, offset: int, limit: int) -> list[dict[str, Any]]:
        """
        Return a sorted page of transactions for the contract.
        """

        items = list(self._transactions[(chain_id, contract_address)].values())
        items.sort(key=lambda item: (item.get("block_number", -1), item.get("transaction_index", -1)))
        return items[offset : offset + limit]

    def get_transactions_count(self, chain_id: int, contract_address: str) -> int:
        """
        Return the number of stored transactions for the contract.
        """

        return len(self._transactions[(chain_id, contract_address)])

    def get_method_transactions(self, chain_id: int, contract_address: str, method_selector: str, offset: int,
                                limit: int) -> list[dict[str, Any]]:
        """
        Return a sorted page of transactions for one contract method selector.
        """

        items = [
            item for item in self._transactions[(chain_id, contract_address)].values()
            if item.get("method_selector") == method_selector
        ]
        items.sort(key=lambda item: (item.get("block_number", -1), item.get("transaction_index", -1)))
        return items[offset : offset + limit]

    def get_method_transactions_count(self, chain_id: int, contract_address: str, method_selector: str) -> int:
        """
        Return the number of stored transactions for one contract method selector.
        """

        return sum(
            1
            for item in self._transactions[(chain_id, contract_address)].values()
            if item.get("method_selector") == method_selector
        )

    def get_contract_events_bookmark(self, chain_id: int, contract_address: str, event: str) -> tuple[int, int, int]:
        """
        Return the event bookmark for a contract and event, or `(-1, -1, -1)`.
        """

        return self._event_bookmarks.get((chain_id, contract_address, event), (-1, -1, -1))

    def set_contract_events_bookmark(self, chain_id: int, contract_address: str, event: str, block_number: int,
                                     transaction_index: int, log_index: int) -> None:
        """
        Store the event bookmark for a contract and event.
        """

        self._event_bookmarks[(chain_id, contract_address, event)] = (block_number, transaction_index, log_index)

    def store_events(self, chain_id: int, contract_address: str, events: list[dict[str, Any]]) -> None:
        """
        Upsert events in memory using their locator tuple as key.
        """

        for event in events:
            event_name = str(event["event"])
            key = (chain_id, contract_address, event_name)
            locator = (int(event.get("block_number", -1)), int(event.get("transaction_index", -1)),
                       int(event.get("log_index", -1)))
            self._events[key][locator] = event

    def get_events(self, chain_id: int, contract_address: str, event: str, offset: int, limit: int)\
            -> list[dict[str, Any]]:
        """
        Return a sorted page of events for the contract and event signature.
        """

        items = list(self._events[(chain_id, contract_address, event)].items())
        items.sort(key=lambda item: item[0])
        return [value for _, value in items[offset : offset + limit]]

    def get_events_count(self, chain_id: int, contract_address: str, event: str) -> int:
        """
        Return the number of stored events for the contract and event signature.
        """

        return len(self._events[(chain_id, contract_address, event)])
