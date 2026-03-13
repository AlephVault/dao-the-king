from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any


class StorageBackend(ABC):
    """
    Abstract storage contract for cache, transactions, and events.
    """

    @abstractmethod
    def get_contract_cache(self, chain_id: int, contract_address: str) -> dict[str, Any] | None:
        """
        Return the cached badge payload for a contract, or `None` if absent.
        """

        raise NotImplementedError

    @abstractmethod
    def set_contract_cache(self, chain_id: int, contract_address: str, cache_object: dict[str, Any]) -> None:
        """
        Persist the cached badge payload for a contract.
        """

        raise NotImplementedError

    @abstractmethod
    def clear_contract_cache(self, chain_id: int, contract_address: str) -> None:
        """
        Remove the cache entry for a single contract.
        """

        raise NotImplementedError

    @abstractmethod
    def clear_chain_contract_cache(self, chain_id: int) -> None:
        """
        Remove all cache entries for one chain.
        """

        raise NotImplementedError

    @abstractmethod
    def clear_all_contracts_cache(self) -> None:
        """
        Remove all contract cache entries across all chains.
        """

        raise NotImplementedError

    @abstractmethod
    def get_contract_transactions_bookmark(self, chain_id: int, contract_address: str) -> tuple[int, int]:
        """
        Return the last stored transaction bookmark, or `(-1, -1)` if absent.
        """

        raise NotImplementedError

    @abstractmethod
    def set_contract_transactions_bookmark(self, chain_id: int, contract_address: str, last_block_number: int,
                                           last_transaction_index: int) -> None:
        """
        Persist the transaction bookmark for a contract.
        """

        raise NotImplementedError

    @abstractmethod
    def store_transactions(self, chain_id: int, contract_address: str, transactions: list[dict[str, Any]]) -> None:
        """
        Insert or upsert transactions for a contract.
        """

        raise NotImplementedError

    @abstractmethod
    def get_transactions(self, chain_id: int, contract_address: str, offset: int, limit: int) -> list[dict[str, Any]]:
        """
        Return a page of stored transactions ordered by block and transaction index.
        """

        raise NotImplementedError

    @abstractmethod
    def get_transactions_count(self, chain_id: int, contract_address: str) -> int:
        """
        Return how many transactions are stored for a contract.
        """

        raise NotImplementedError

    @abstractmethod
    def get_method_transactions(self, chain_id: int, contract_address: str, method_selector: str, offset: int,
                                limit: int) -> list[dict[str, Any]]:
        """
        Return a page of stored transactions for one contract method selector.
        """

        raise NotImplementedError

    @abstractmethod
    def get_method_transactions_count(self, chain_id: int, contract_address: str, method_selector: str) -> int:
        """
        Return how many transactions are stored for one contract method selector.
        """

        raise NotImplementedError

    @abstractmethod
    def get_contract_events_bookmark(self, chain_id: int, contract_address: str, event: str) -> tuple[int, int, int]:
        """
        Return the last stored event bookmark, or `(-1, -1, -1)` if absent.
        """

        raise NotImplementedError

    @abstractmethod
    def set_contract_events_bookmark(self, chain_id: int, contract_address: str, event: str, block_number: int,
                                     transaction_index: int, log_index: int) -> None:
        """
        Persist the event bookmark for a contract and full event signature.
        """

        raise NotImplementedError

    @abstractmethod
    def store_events(self, chain_id: int, contract_address: str, events: list[dict[str, Any]]) -> None:
        """
        Insert or upsert events for a contract.
        """

        raise NotImplementedError

    @abstractmethod
    def get_events(self, chain_id: int, contract_address: str, event: str, offset: int, limit: int)\
            -> list[dict[str, Any]]:
        """
        Return a page of stored events ordered by block, transaction, and log index.
        """

        raise NotImplementedError

    @abstractmethod
    def get_events_count(self, chain_id: int, contract_address: str, event: str) -> int:
        """
        Return how many events are stored for a contract and event signature.
        """

        raise NotImplementedError
