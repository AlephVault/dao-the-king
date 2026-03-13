from __future__ import annotations
from typing import Any
import streamlit as st
from web3 import Web3


def render_parameter_input(parameter: dict[str, Any], key: str) -> tuple[Any, str | None]:
    """
    Render one ABI parameter input widget and return its parsed value plus error.

    The returned value is shaped to be passed directly into `contract.functions`
    calls whenever possible. Validation errors are returned separately so the
    caller can aggregate them and disable execution.
    """

    type_name = str(parameter.get("type", ""))
    label = str(parameter.get("name") or type_name or "value")

    # Arrays must be handled before scalar prefixes such as `bytes` or `tuple`.
    if _is_array_type(type_name):
        return _render_array_input(parameter, key)
    if type_name == "tuple":
        return _render_tuple_input(parameter, key)
    if type_name == "bool":
        return st.checkbox(label, key=key), None
    if type_name == "string":
        return st.text_input(label, key=key), None
    if type_name == "address":
        return _render_address_input(label, key)
    if _is_integer_type(type_name):
        return _render_integer_input(type_name, label, key)
    if _is_bytes_type(type_name):
        return _render_bytes_input(type_name, label, key)
    return st.text_input(label, key=key), None


def _render_tuple_input(parameter: dict[str, Any], key: str) -> tuple[Any, str | None]:
    """
    Render a tuple parameter by recursively rendering each component.
    """

    values: list[Any] = []
    errors: list[str] = []
    with st.container(border=True):
        st.caption(str(parameter.get("name") or "tuple"))
        for index, component in enumerate(parameter.get("components", [])):
            if not isinstance(component, dict):
                values.append(None)
                errors.append(f"Invalid tuple component at index {index}")
                continue
            value, error = render_parameter_input(component, f"{key}:{index}")
            values.append(value)
            if error:
                component_name = str(component.get("name") or index)
                errors.append(f"{component_name}: {error}")
    return values, "; ".join(errors) if errors else None


def _render_array_input(parameter: dict[str, Any], key: str) -> tuple[Any, str | None]:
    """
    Render one ABI array parameter, including nested arrays and tuple arrays.
    """

    label = str(parameter.get("name") or "array")
    element_parameter, fixed_length = _array_element_parameter(parameter)
    if fixed_length is None:
        length = int(st.number_input(f"{label} length", min_value=0, step=1, key=f"{key}:length"))
    else:
        length = fixed_length

    values: list[Any] = []
    errors: list[str] = []
    with st.container(border=True):
        st.caption(f"{label}[{length}]")
        for index in range(length):
            value, error = render_parameter_input(element_parameter, f"{key}:{index}")
            values.append(value)
            if error:
                errors.append(f"{index}: {error}")
    return values, "; ".join(errors) if errors else None


def _render_address_input(label: str, key: str) -> tuple[str, str | None]:
    """
    Render one address parameter input with EVM address validation.
    """

    value = st.text_input(label, key=key, placeholder="0x...")
    if Web3.is_address(value):
        return value, None
    return value, "Expected EVM address"


def _render_integer_input(type_name: str, label: str, key: str) -> tuple[int | None, str | None]:
    """
    Render one integer parameter input and validate its signedness.
    """

    value = st.text_input(label, key=key, value="0")
    try:
        parsed = int(value, 10)
    except ValueError:
        return None, "Expected integer"
    if type_name.startswith("uint") and parsed < 0:
        return None, "Expected unsigned integer"
    return parsed, None


def _render_bytes_input(type_name: str, label: str, key: str) -> tuple[str, str | None]:
    """
    Render one bytes parameter input and validate hex formatting and width.
    """

    value = st.text_area(label, key=key, placeholder="0x...")
    if not value.startswith("0x"):
        return value, "Expected hex string"
    payload = value[2:]
    if len(payload) % 2 != 0:
        return value, "Expected even-length hex string"

    if type_name != "bytes":
        expected_size = int(type_name[5:])
        if len(payload) != expected_size * 2:
            return value, f"Expected {expected_size} bytes"
    return value, None


def _is_array_type(type_name: str) -> bool:
    """
    Tell whether an ABI type includes at least one array suffix.
    """

    return "[" in type_name


def _is_integer_type(type_name: str) -> bool:
    """
    Tell whether an ABI type is one of the signed or unsigned integer families.
    """

    return type_name.startswith("uint") or type_name.startswith("int")


def _is_bytes_type(type_name: str) -> bool:
    """
    Tell whether an ABI type is `bytes` or one of the fixed-size `bytesN` types.
    """

    return type_name == "bytes" or type_name.startswith("bytes")


def _array_element_parameter(parameter: dict[str, Any]) -> tuple[dict[str, Any], int | None]:
    """
    Build the ABI parameter definition for one array element plus its fixed size.

    The returned parameter preserves tuple components and any remaining nested
    array suffix so recursive rendering can continue naturally.
    """

    type_name = str(parameter.get("type", ""))
    start = type_name.index("[")
    end = type_name.index("]")
    length_text = type_name[start + 1 : end]
    element_type = f"{type_name[:start]}{type_name[end + 1:]}"

    element_parameter = dict(parameter)
    element_parameter["type"] = element_type
    fixed_length = int(length_text) if length_text else None
    return element_parameter, fixed_length
