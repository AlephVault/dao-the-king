import json
import pytest

from daotheking.core.contracts import known_abis
from daotheking.core.contracts.loader import _validate_abi_payload, load_contracts
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


def test_validate_abi_payload_accepts_known_good_erc20_abi() -> None:
    _validate_abi_payload(known_abis.ERC20 + known_abis.ERC20Metadata)


def test_validate_abi_payload_rejects_function_without_outputs() -> None:
    with pytest.raises(ValueError, match="outputs must be a list"):
        _validate_abi_payload(
            [
                {
                    "type": "function",
                    "name": "balanceOf",
                    "inputs": [{"name": "account", "type": "address"}],
                    "stateMutability": "view",
                }
            ]
        )


def test_validate_abi_payload_rejects_non_tuple_components_mismatch() -> None:
    with pytest.raises(ValueError, match="components must be present if and only if the type is tuple-based"):
        _validate_abi_payload(
            [
                {
                    "type": "function",
                    "name": "broken",
                    "inputs": [{"name": "value", "type": "uint256", "components": []}],
                    "outputs": [],
                    "stateMutability": "nonpayable",
                }
            ]
        )


def test_validate_abi_payload_rejects_receive_with_non_payable_state() -> None:
    with pytest.raises(ValueError, match="must be payable for receive entries"):
        _validate_abi_payload(
            [
                {
                    "type": "receive",
                    "stateMutability": "nonpayable",
                }
            ]
        )


def test_validate_abi_payload_rejects_invalid_parameter_base_type() -> None:
    with pytest.raises(ValueError, match="invalid base type"):
        _validate_abi_payload(
            [
                {
                    "type": "function",
                    "name": "broken",
                    "inputs": [{"name": "value", "type": "uint7"}],
                    "outputs": [],
                    "stateMutability": "nonpayable",
                }
            ]
        )


def test_validate_abi_payload_rejects_invalid_parameter_array_suffix() -> None:
    with pytest.raises(ValueError, match="invalid array length"):
        _validate_abi_payload(
            [
                {
                    "type": "function",
                    "name": "broken",
                    "inputs": [{"name": "value", "type": "uint256[abc]"}],
                    "outputs": [],
                    "stateMutability": "nonpayable",
                }
            ]
        )


def test_validate_abi_payload_accepts_valid_parameter_array_suffixes() -> None:
    _validate_abi_payload(
        [
            {
                "type": "function",
                "name": "ok",
                "inputs": [
                    {"name": "a", "type": "uint256[]"},
                    {"name": "b", "type": "bytes32[2][3][]"},
                    {"name": "c", "type": "tuple[][1]", "components": [{"name": "x", "type": "address"}]},
                ],
                "outputs": [],
                "stateMutability": "nonpayable",
            }
        ]
    )
