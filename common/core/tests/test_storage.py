from daotheking.core.storage import InMemoryStorage


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
