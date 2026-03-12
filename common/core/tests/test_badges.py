from copy import deepcopy

from daotheking.core.contracts import known_abis
from daotheking.core.contracts.badges import _events_metadata, _functions_metadata, _match_known_badges


def test_match_known_badges_ignores_parameter_names() -> None:
    abi = deepcopy(known_abis.ERC20)
    for entry in abi:
        for parameter in entry.get("inputs", []):
            parameter.pop("name", None)
        for parameter in entry.get("outputs", []):
            parameter.pop("name", None)
    assert "ERC20" in _match_known_badges(abi)


def test_functions_metadata_uses_sorted_signatures() -> None:
    functions = _functions_metadata(known_abis.ERC20[:])
    assert functions[0][0] == "function allowance(address owner, address spender) external view returns (uint256)"
    assert functions[-1][0] == "function transferFrom(address from, address to, uint256 value) external returns (bool)"


def test_events_metadata_uses_sorted_signatures() -> None:
    events = _events_metadata(known_abis.ERC20[:])
    assert events[0][0] == "event Approval(address indexed owner, address indexed spender, uint256 value)"
    assert events[1][0] == "event Transfer(address indexed from, address indexed to, uint256 value)"
