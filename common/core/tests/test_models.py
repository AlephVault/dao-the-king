import pytest
from pydantic import ValidationError

from daotheking.core.contracts.models import ContractsFile


def test_contracts_file_accepts_chain_id_object_keys() -> None:
    payload = {
        "1": {
            "name": "Ethereum",
            "rpc": "https://ethereum.example",
            "contracts": [],
        }
    }
    parsed = ContractsFile.model_validate(payload)
    assert 1 in parsed.chains


def test_contracts_file_requires_https_rpc() -> None:
    payload = {
        "1": {
            "name": "Ethereum",
            "rpc": "http://ethereum.example",
            "contracts": [],
        }
    }
    with pytest.raises(ValidationError):
        ContractsFile.model_validate(payload)
