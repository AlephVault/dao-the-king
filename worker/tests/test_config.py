from __future__ import annotations

import logging

from daotheking.core.contracts.models import ChainEntry, ContractEntry, ContractRetrieveSpec
from daotheking.worker.config import ContractRuntimeConfig, iter_requested_events


def _runtime(events):
    return ContractRuntimeConfig(
        chain_id=1,
        chain=ChainEntry(name="Ethereum", rpc="https://ethereum.example", contracts=[]),
        contract=ContractEntry(
            address="0x0000000000000000000000000000000000000000",
            retrieve=ContractRetrieveSpec(events=events),
        ),
    )


def test_iter_requested_events_matches_simple_name_and_deduplicates() -> None:
    runtime = _runtime({"Transfer": True, "Transfer(address,address,uint256)": True})
    abi = [
        {
            "type": "event",
            "name": "Transfer",
            "inputs": [
                {"type": "address", "name": "from", "indexed": True},
                {"type": "address", "name": "to", "indexed": True},
                {"type": "uint256", "name": "value", "indexed": False},
            ],
        }
    ]
    assert list(iter_requested_events(runtime, abi)) == [("Transfer(address,address,uint256)", True)]


def test_iter_requested_events_warns_for_unmatched_selector(caplog) -> None:
    runtime = _runtime({"Missing": True})
    with caplog.at_level(logging.WARNING):
        resolved = list(iter_requested_events(runtime, []))
    assert resolved == []
    assert "did not match any ABI event" in caplog.text
