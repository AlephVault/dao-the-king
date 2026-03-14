from daotheking.core.storage import InMemoryStorage
from daotheking.core.storage.mongodb import _mongo_safe_value


def test_in_memory_storage_transactions_are_sorted() -> None:
    storage = InMemoryStorage()
    storage.store_transactions(
        1,
        "0x1",
        [
            {"hash": "0xb", "block_number": 2, "transaction_index": 0},
            {"hash": "0xa", "block_number": 1, "transaction_index": 1},
        ],
    )
    items = storage.get_transactions(1, "0x1", 0, 10)
    assert [item["hash"] for item in items] == ["0xa", "0xb"]


def test_in_memory_storage_transactions_can_be_filtered_by_method_selector() -> None:
    storage = InMemoryStorage()
    storage.store_transactions(
        1,
        "0x1",
        [
            {"hash": "0xa", "block_number": 1, "transaction_index": 1, "method_selector": "0x11111111"},
            {"hash": "0xb", "block_number": 2, "transaction_index": 0, "method_selector": "0x22222222"},
            {"hash": "0xc", "block_number": 3, "transaction_index": 0, "method_selector": "0x11111111"},
        ],
    )

    assert storage.get_method_transactions_count(1, "0x1", "0x11111111") == 2
    items = storage.get_method_transactions(1, "0x1", "0x11111111", 0, 10)
    assert [item["hash"] for item in items] == ["0xa", "0xc"]


def test_mongo_safe_value_stringifies_nested_integers() -> None:
    result = _mongo_safe_value(
        {
            "value": 2**256 - 1,
            "nested": {"count": 7, "flag": True},
            "items": [1, False, {"x": 3}],
        }
    )

    assert result == {
        "value": str(2**256 - 1),
        "nested": {"count": "7", "flag": True},
        "items": ["1", False, {"x": "3"}],
    }
