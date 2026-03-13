from __future__ import annotations

from types import SimpleNamespace

from daotheking.worker.config import WorkerSettings
from daotheking.worker.service import WorkerContext, WorkerService


class _DummyStorage:
    pass


def _context() -> WorkerContext:
    return WorkerContext(
        settings=WorkerSettings(
            mongodb_uri="mongodb://example",
            mongodb_database="db",
            etherscan_api_key=None,
            contracts_file_path="/tmp/contracts.json",
            run_once=False,
        ),
        storage=_DummyStorage(),  # type: ignore[arg-type]
        runtime_configs=[],
        contracts={},
    )


def test_event_storage_key_is_keccak_hex() -> None:
    key = WorkerService._event_storage_key("Transfer(address,address,uint256)")
    assert key.startswith("0x")
    assert len(key) == 66


def test_should_store_sampled_respects_minimum() -> None:
    service = WorkerService(_context())
    assert service._should_store_sampled(0, 0.0, 2) is True
    assert service._should_store_sampled(1, 0.0, 2) is True


def test_run_returns_error_when_no_threads_started() -> None:
    service = WorkerService(_context())
    assert service.run() == 1


def test_normalize_transaction_includes_result_and_receipt() -> None:
    receipt = {"status": 1}
    contract = SimpleNamespace(
        address="0x0000000000000000000000000000000000000000",
        w3=SimpleNamespace(eth=SimpleNamespace(get_transaction_receipt=lambda _: receipt)),
        decode_function_input=lambda _: (_DummyFunctionAbi("transfer", {
            "name": "transfer",
            "inputs": [
                {"type": "address", "name": "to"},
                {"type": "uint256", "name": "value"},
            ],
        }), {"to": "0x1", "value": 2}),
    )
    runtime = SimpleNamespace(chain_id=1)
    transaction = {
        "hash": "0xabc",
        "blockNumber": 10,
        "transactionIndex": 3,
        "input": "0xa9059cbb00000000",
    }
    normalized = WorkerService._normalize_transaction(runtime, contract, transaction)
    assert normalized["result"] == {"status": 1}
    assert normalized["receipt"] == {"status": 1}
    assert normalized["decoded_input"]["function_name"] == "transfer"
    assert normalized["decoded_input"]["function_signature"] == "transfer(address,uint256)"
    assert normalized["method_selector"] == "0xa9059cbb"
    assert normalized["decoded_input"]["method_selector"] == "0xa9059cbb"


def test_normalize_event_uses_hash_as_primary_identity(monkeypatch) -> None:
    log = {
        "blockNumber": 10,
        "transactionIndex": 3,
        "logIndex": 1,
        "transactionHash": SimpleNamespace(hex=lambda: "0xaaa"),
    }
    monkeypatch.setattr(
        "daotheking.worker.service.get_event_data",
        lambda _codec, _abi, _log: {"args": {"value": 1}},
    )
    contract = SimpleNamespace(
        address="0x0000000000000000000000000000000000000000",
        w3=SimpleNamespace(codec=object()),
    )
    normalized = WorkerService._normalize_event(
        contract,
        "Transfer(address,address,uint256)",
        {"type": "event", "name": "Transfer", "inputs": []},
        log,
    )
    assert normalized["event"] == normalized["event_hash"]
    assert normalized["event_signature"] == "Transfer(address,address,uint256)"


class _DummyFunctionAbi:
    def __init__(self, fn_name: str, abi: dict[str, object]) -> None:
        self.fn_name = fn_name
        self.abi = abi
