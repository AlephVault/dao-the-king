from __future__ import annotations

from typing import Any

from .base import StorageBackend


class MongoDBStorage(StorageBackend):
    """MongoDB-backed storage.

    This backend keeps `pymongo` optional. Import errors are raised only when
    this backend is instantiated.
    """

    def __init__(self, database: Any) -> None:
        """
        Bind the backend to a MongoDB database handle and create indexes.
        """

        self._database = database
        self._contract_cache = database["contract_cache"]
        self._transaction_bookmarks = database["transaction_bookmarks"]
        self._transactions = database["transactions"]
        self._event_bookmarks = database["event_bookmarks"]
        self._events = database["events"]
        self._ensure_indexes()

    @classmethod
    def from_uri(cls, uri: str, database_name: str, **client_kwargs: Any) -> "MongoDBStorage":
        """
        Create a backend from a MongoDB connection URI and database name.
        """

        pymongo = _import_pymongo()
        client = pymongo.MongoClient(uri, **client_kwargs)
        return cls(client[database_name])

    def _ensure_indexes(self) -> None:
        """
        Create the indexes needed for unique upserts and ordered pagination.
        """

        self._contract_cache.create_index(
            [("chain_id", 1), ("contract_address", 1)],
            unique=True,
            name="contract_cache_chain_address",
        )
        self._transaction_bookmarks.create_index(
            [("chain_id", 1), ("contract_address", 1)],
            unique=True,
            name="transaction_bookmarks_chain_address",
        )
        self._transactions.create_index(
            [("chain_id", 1), ("contract_address", 1), ("hash", 1)],
            unique=True,
            name="transactions_chain_address_hash",
        )
        self._transactions.create_index(
            [("chain_id", 1), ("contract_address", 1), ("block_number", 1), ("transaction_index", 1)],
            name="transactions_chain_address_order",
        )
        self._transactions.create_index(
            [("chain_id", 1), ("contract_address", 1), ("method_selector", 1), ("block_number", 1),
             ("transaction_index", 1)],
            name="transactions_chain_address_method_order",
        )
        self._event_bookmarks.create_index(
            [("chain_id", 1), ("contract_address", 1), ("event", 1)],
            unique=True,
            name="event_bookmarks_chain_address_event",
        )
        self._events.create_index(
            [("chain_id", 1), ("contract_address", 1), ("event", 1), ("block_number", 1), ("transaction_index", 1),
             ("log_index", 1)],
            unique=True,
            name="events_chain_address_event_locator",
        )

    def get_contract_cache(self, chain_id: int, contract_address: str) -> dict[str, Any] | None:
        """
        Return the cached badge payload for a contract, if present.
        """

        document = self._contract_cache.find_one(
            {"chain_id": chain_id, "contract_address": contract_address}
        )
        return _strip_id(document)

    def set_contract_cache(self, chain_id: int, contract_address: str, cache_object: dict[str, Any]) -> None:
        """
        Store or replace the cached badge payload for a contract.
        """

        sanitized_cache = _mongo_safe_value(cache_object)
        self._contract_cache.update_one(
            {"chain_id": chain_id, "contract_address": contract_address},
            {
                "$set": {
                    "chain_id": chain_id,
                    "contract_address": contract_address,
                    **sanitized_cache,
                }
            },
            upsert=True,
        )

    def clear_contract_cache(self, chain_id: int, contract_address: str) -> None:
        """
        Delete the cache entry for a single contract.
        """

        self._contract_cache.delete_one({"chain_id": chain_id, "contract_address": contract_address})

    def clear_chain_contract_cache(self, chain_id: int) -> None:
        """
        Delete every cache entry associated with one chain.
        """

        self._contract_cache.delete_many({"chain_id": chain_id})

    def clear_all_contracts_cache(self) -> None:
        """
        Delete every cached contract badge payload.
        """

        self._contract_cache.delete_many({})

    def get_contract_transactions_bookmark(self, chain_id: int, contract_address: str) -> tuple[int, int]:
        """
        Return the transaction bookmark for a contract, or `(-1, -1)`.
        """

        document = self._transaction_bookmarks.find_one(
            {"chain_id": chain_id, "contract_address": contract_address}
        )
        if document is None:
            return -1, -1
        return int(document["last_block_number"]), int(document["last_transaction_index"])

    def set_contract_transactions_bookmark(self, chain_id: int, contract_address: str, last_block_number: int,
                                           last_transaction_index: int) -> None:
        """
        Store the transaction bookmark for a contract.
        """

        self._transaction_bookmarks.update_one(
            {"chain_id": chain_id, "contract_address": contract_address},
            {
                "$set": {
                    "chain_id": chain_id,
                    "contract_address": contract_address,
                    "last_block_number": last_block_number,
                    "last_transaction_index": last_transaction_index,
                }
            },
            upsert=True,
        )

    def store_transactions(self, chain_id: int, contract_address: str, transactions: list[dict[str, Any]]) -> None:
        """
        Bulk upsert transactions using `(chain, address, hash)` as identity.
        """

        if not transactions:
            return
        pymongo = _import_pymongo()
        operations = []
        for transaction in transactions:
            tx_hash = str(transaction["hash"])
            payload = _mongo_safe_value({
                "chain_id": chain_id,
                "contract_address": contract_address,
                "hash": tx_hash,
                **transaction,
            })
            payload["chain_id"] = chain_id
            payload["contract_address"] = contract_address
            payload["hash"] = tx_hash
            payload["block_number"] = int(transaction["block_number"])
            payload["transaction_index"] = int(transaction["transaction_index"])
            operations.append(
                pymongo.UpdateOne(
                    {"chain_id": chain_id, "contract_address": contract_address, "hash": tx_hash},
                    {"$set": payload},
                    upsert=True,
                )
            )
        self._transactions.bulk_write(operations, ordered=False)

    def get_transactions(self, chain_id: int, contract_address: str, offset: int, limit: int) -> list[dict[str, Any]]:
        """
        Return a sorted page of transactions for the contract.
        """

        cursor = (
            self._transactions.find({"chain_id": chain_id, "contract_address": contract_address})
            .sort([("block_number", 1), ("transaction_index", 1)])
            .skip(offset)
            .limit(limit)
        )
        return [_strip_id(document) for document in cursor]

    def get_transactions_count(self, chain_id: int, contract_address: str) -> int:
        """
        Return the number of stored transactions for the contract.
        """

        return int(self._transactions.count_documents({"chain_id": chain_id, "contract_address": contract_address}))

    def get_method_transactions(self, chain_id: int, contract_address: str, method_selector: str, offset: int,
                                limit: int) -> list[dict[str, Any]]:
        """
        Return a sorted page of transactions for one contract method selector.
        """

        cursor = (
            self._transactions.find(
                {
                    "chain_id": chain_id,
                    "contract_address": contract_address,
                    "method_selector": method_selector,
                }
            )
            .sort([("block_number", 1), ("transaction_index", 1)])
            .skip(offset)
            .limit(limit)
        )
        return [_strip_id(document) for document in cursor]

    def get_method_transactions_count(self, chain_id: int, contract_address: str, method_selector: str) -> int:
        """
        Return the number of stored transactions for one contract method selector.
        """

        return int(
            self._transactions.count_documents(
                {
                    "chain_id": chain_id,
                    "contract_address": contract_address,
                    "method_selector": method_selector,
                }
            )
        )

    def get_contract_events_bookmark(self, chain_id: int, contract_address: str, event: str) -> tuple[int, int, int]:
        """
        Return the event bookmark for a contract and event, or `(-1, -1, -1)`.
        """

        document = self._event_bookmarks.find_one(
            {"chain_id": chain_id, "contract_address": contract_address, "event": event}
        )
        if document is None:
            return -1, -1, -1
        return (
            int(document["block_number"]),
            int(document["transaction_index"]),
            int(document["log_index"]),
        )

    def set_contract_events_bookmark(self, chain_id: int, contract_address: str, event: str, block_number: int,
                                     transaction_index: int, log_index: int) -> None:
        """
        Store the event bookmark for a contract and event.
        """

        self._event_bookmarks.update_one(
            {"chain_id": chain_id, "contract_address": contract_address, "event": event},
            {
                "$set": {
                    "chain_id": chain_id,
                    "contract_address": contract_address,
                    "event": event,
                    "block_number": block_number,
                    "transaction_index": transaction_index,
                    "log_index": log_index,
                }
            },
            upsert=True,
        )

    def store_events(self, chain_id: int, contract_address: str, events: list[dict[str, Any]]) -> None:
        """
        Bulk upsert events using their locator tuple as identity.
        """

        if not events:
            return
        pymongo = _import_pymongo()
        operations = []
        for event in events:
            event_name = str(event["event"])
            locator = {
                "block_number": int(event.get("block_number", -1)),
                "transaction_index": int(event.get("transaction_index", -1)),
                "log_index": int(event.get("log_index", -1)),
            }
            payload = _mongo_safe_value({
                "chain_id": chain_id,
                "contract_address": contract_address,
                "event": event_name,
                **locator,
                **event,
            })
            payload["chain_id"] = chain_id
            payload["contract_address"] = contract_address
            payload["event"] = event_name
            payload.update(locator)
            operations.append(
                pymongo.UpdateOne(
                    {
                        "chain_id": chain_id,
                        "contract_address": contract_address,
                        "event": event_name,
                        **locator,
                    },
                    {"$set": payload},
                    upsert=True,
                )
            )
        self._events.bulk_write(operations, ordered=False)

    def get_events(self, chain_id: int, contract_address: str, event: str, offset: int, limit: int)\
            -> list[dict[str, Any]]:
        """
        Return a sorted page of events for the contract and event signature.
        """

        cursor = (
            self._events.find({"chain_id": chain_id, "contract_address": contract_address, "event": event})
            .sort([("block_number", 1), ("transaction_index", 1), ("log_index", 1)])
            .skip(offset)
            .limit(limit)
        )
        return [_strip_id(document) for document in cursor]

    def get_events_count(self, chain_id: int, contract_address: str, event: str) -> int:
        """
        Return the number of stored events for the contract and event signature.
        """

        return int(
            self._events.count_documents(
                {"chain_id": chain_id, "contract_address": contract_address, "event": event}
            )
        )


def _import_pymongo() -> Any:
    """
    Import `pymongo` lazily so the core package keeps MongoDB optional.
    """

    try:
        import pymongo
    except ImportError as exc:
        raise RuntimeError(
            "MongoDBStorage requires `pymongo` to be installed in the runtime environment."
        ) from exc
    return pymongo


def _strip_id(document: dict[str, Any] | None) -> dict[str, Any] | None:
    """
    Return a shallow copy of a MongoDB document without its internal `_id`.
    """

    if document is None:
        return None
    result = dict(document)
    result.pop("_id", None)
    return result


def _mongo_safe_value(value: Any) -> Any:
    """
    Convert nested values into MongoDB-safe primitives while preserving
    top-level locator fields that callers explicitly restore after sanitizing.
    """

    if isinstance(value, dict):
        return {str(key): _mongo_safe_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_mongo_safe_value(item) for item in value]
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
