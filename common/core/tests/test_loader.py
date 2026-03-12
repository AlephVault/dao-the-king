import json

from daotheking.core.contracts.loader import load_contracts
from daotheking.core.contracts.models import ContractLoadError


def test_load_contracts_returns_invalid_abi_for_malformed_abi_file(tmp_path) -> None:
    abi_file = tmp_path / "abi.json"
    abi_file.write_text(json.dumps([123]), encoding="utf-8")

    contracts_file = tmp_path / "contracts.json"
    contracts_file.write_text(
        json.dumps(
            {
                "1": {
                    "name": "Ethereum",
                    "rpc": "https://ethereum.example",
                    "contracts": [
                        {
                            "address": "0x0000000000000000000000000000000000000000",
                            "abi": str(abi_file),
                        }
                    ],
                }
            }
        ),
        encoding="utf-8",
    )

    results, error = load_contracts(contracts_file_path=str(contracts_file))

    assert error is None
    assert results[1]["0x0000000000000000000000000000000000000000"].error == ContractLoadError.NO_API_KEY_FOR_VERIFICATION
