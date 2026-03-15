from __future__ import annotations

import json
from math import ceil
from typing import Any

import streamlit as st
from web3 import Web3
from web3.contract import Contract

from daotheking.core.contracts.loader import ContractLoadResult

from .abi import format_event_signature, format_function_signature, format_topic_signature, function_key
from .data import ServerData, function_entries
from .forms import render_parameter_input
from .navigation import app_url, chain_label, render_breadcrumbs, set_query_params
from .wallet import WalletView, render_chain_wallet_prompt


def render_main_page(data: ServerData) -> None:
    """
    Render the landing page with the supported chains list.
    """

    st.header("Welcome")
    st.write(
        "Dao The King lets you browse supported chains, inspect configured contracts, "
        "review stored transactions and events, and interact with contract methods through your browser wallet."
    )
    st.subheader("Supported Chains")
    for chain_id in sorted(data.contracts):
        st.markdown(f"- [{chain_label(data, chain_id)}]({app_url(chain_id=chain_id)})")


def render_chain_page(data: ServerData, wallet_view: WalletView, chain_id: int) -> None:
    """
    Render the per-chain page with its contract list.
    """

    render_breadcrumbs([("Supported Chains", app_url())])
    st.header(chain_label(data, chain_id))
    render_chain_wallet_prompt(wallet_view, expected_chain_id=chain_id)
    st.subheader("Supported Contracts")
    for address in sorted(data.contracts[chain_id]):
        st.markdown(f"- [{address}]({app_url(chain_id=chain_id, contract=address)})")


def render_contract_page(
    data: ServerData,
    wallet_view: WalletView,
    chain_id: int,
    contract_address: str,
    result: ContractLoadResult,
) -> None:
    """
    Render the contract overview page.
    """

    render_breadcrumbs(
        [
            ("Supported Chains", app_url()),
            (str(chain_id), app_url(chain_id=chain_id)),
        ]
    )
    st.header(contract_address)
    st.caption(chain_label(data, chain_id))
    render_chain_wallet_prompt(wallet_view, expected_chain_id=chain_id)

    if result.error is not None or result.contract is None:
        st.error(f"Contract could not be loaded: {result.error}")
        _render_warnings(result.warnings)
        return

    contract = result.contract
    badges = result.badges.badges if result.badges else {}
    _render_warnings(result.warnings)

    left, right = st.columns([2, 1])
    with left:
        st.write("Badges")
        st.json(badges)
    with right:
        if "ERC1967" in badges:
            st.write("Proxy Slots")
            st.json(badges["ERC1967"])

    functions = function_entries(contract)
    badge_options = ["All"] + sorted(badge for badge in badges if badge in data.badge_methods)
    selected_badge = st.selectbox("Filter methods by badge", badge_options)
    if selected_badge != "All":
        allowed = data.badge_methods[selected_badge]
        functions = [entry for entry in functions if function_key(entry) in allowed]

    st.subheader("Methods")
    for entry in functions:
        signature = format_function_signature(entry)
        if st.button(signature, key=f"method:{chain_id}:{contract_address}:{function_key(entry)}"):
            set_query_params(chain_id=chain_id, contract=contract_address, method=function_key(entry))

    render_transactions_section(data, chain_id, contract_address)
    render_events_section(data, chain_id, contract_address, contract)


def render_method_page(
    data: ServerData,
    wallet_view: WalletView,
    chain_id: int,
    contract_address: str,
    result: ContractLoadResult,
    method_key: str,
) -> None:
    """
    Render the method interaction page.
    """

    render_breadcrumbs(
        [
            ("Supported Chains", app_url()),
            (str(chain_id), app_url(chain_id=chain_id)),
            (contract_address, app_url(chain_id=chain_id, contract=contract_address)),
        ]
    )
    st.caption(chain_label(data, chain_id))
    render_chain_wallet_prompt(wallet_view, expected_chain_id=chain_id)

    if result.error is not None or result.contract is None:
        st.error(f"Contract could not be loaded: {result.error}")
        _render_warnings(result.warnings)
        return

    contract = result.contract
    entry = next((item for item in function_entries(contract) if function_key(item) == method_key), None)
    if entry is None:
        st.error(f"Unknown method `{method_key}`.")
        return

    st.header(format_function_signature(entry))
    _render_warnings(result.warnings)

    args: list[Any] = []
    errors: list[str] = []
    for index, parameter in enumerate(entry.get("inputs", [])):
        value, error = render_parameter_input(parameter, f"method:{method_key}:{index}")
        args.append(value)
        if error:
            errors.append(f"{parameter.get('name') or index}: {error}")

    if wallet_view.connected and wallet_view.selected_account:
        st.caption(f"Selected wallet account: {wallet_view.selected_account}")

    if errors:
        st.error("; ".join(errors))

    state_mutability = entry.get("stateMutability")
    is_read_only = state_mutability in {"view", "pure"}
    if is_read_only:
        _render_call_action(
            contract,
            entry,
            args,
            wallet_view.selected_account,
            errors,
            method_key,
        )
    else:
        _render_send_action(
            chain_id,
            contract_address,
            contract,
            entry,
            args,
            wallet_view,
            errors,
            method_key,
        )

    render_transactions_section(data, chain_id, contract_address, method_key_filter=method_key)


def render_transactions_section(
    data: ServerData,
    chain_id: int,
    contract_address: str,
    method_key_filter: str | None = None,
) -> None:
    """
    Render the stored transactions section for a contract or one method.
    """

    st.subheader("Transactions")
    if method_key_filter is None:
        total_count = data.storage.get_transactions_count(chain_id, contract_address)
        total_pages = max(1, ceil(total_count / data.settings.transactions_page_size))
        page = int(
            st.number_input(
                "Transactions page",
                min_value=1,
                max_value=total_pages,
                step=1,
                key=f"tx-page:{chain_id}:{contract_address}:all",
            )
        )
        offset = (page - 1) * data.settings.transactions_page_size
        items = data.storage.get_transactions(chain_id, contract_address, offset, data.settings.transactions_page_size)
        st.caption(f"Showing {len(items)} of {total_count} transaction(s)")
    else:
        method_selector = _function_selector(method_key_filter)
        total_count = data.storage.get_method_transactions_count(chain_id, contract_address, method_selector)
        total_pages = max(1, ceil(total_count / data.settings.transactions_page_size))
        page = int(
            st.number_input(
                "Transactions page",
                min_value=1,
                max_value=total_pages,
                step=1,
                key=f"tx-page:{chain_id}:{contract_address}:{method_key_filter}",
            )
        )
        offset = (page - 1) * data.settings.transactions_page_size
        items = data.storage.get_method_transactions(
            chain_id,
            contract_address,
            method_selector,
            offset,
            data.settings.transactions_page_size,
        )
        st.caption(f"Showing {len(items)} of {total_count} transaction(s) for `{method_key_filter}`")

    for item in items:
        st.json(item)


def render_events_section(data: ServerData, chain_id: int, contract_address: str, contract: Contract) -> None:
    """
    Render the stored event logs page for one contract.
    """

    st.subheader("Event Logs")
    event_entries = [entry for entry in contract.abi if entry.get("type") == "event"]
    if not event_entries:
        st.info("No events declared in ABI.")
        return

    options = {format_event_signature(entry): format_topic_signature(entry) for entry in event_entries}
    selected_label = st.selectbox("Event", sorted(options), key=f"event-select:{chain_id}:{contract_address}")
    event_key = _event_storage_key(options[selected_label])
    count = data.storage.get_events_count(chain_id, contract_address, event_key)
    total_pages = max(1, ceil(count / data.settings.events_page_size))
    page = int(
        st.number_input(
            "Events page",
            min_value=1,
            max_value=total_pages,
            step=1,
            key=f"event-page:{chain_id}:{contract_address}:{event_key}",
        )
    )
    offset = (page - 1) * data.settings.events_page_size
    items = data.storage.get_events(chain_id, contract_address, event_key, offset, data.settings.events_page_size)
    st.caption(f"Showing {len(items)} of {count} event(s)")
    for item in items:
        st.json(item)


def _render_call_action(
    contract: Contract,
    entry: dict[str, Any],
    args: list[Any],
    from_account: str | None,
    errors: list[str],
    method_key: str,
) -> None:
    """
    Render and execute a read-only contract call.
    """

    state_key = f"call-result:{method_key}"
    state = st.session_state.setdefault(state_key, {"status": None, "message": None})
    if st.button("Execute call", key=f"call:{method_key}", disabled=bool(errors)):
        call_kwargs = {"from": Web3.to_checksum_address(from_account)} if from_account else None
        try:
            result = getattr(contract.functions, entry["name"])(*args).call(call_kwargs)
        except Exception as exc:
            state["status"] = "error"
            state["message"] = str(exc)
        else:
            state["status"] = "success"
            state["message"] = json.dumps(_json_safe(result), indent=2)

    if state["status"] == "error" and state["message"]:
        st.error(state["message"])
    elif state["status"] == "success" and state["message"]:
        st.code(state["message"], language="json")


def _render_send_action(
    chain_id: int,
    contract_address: str,
    contract: Contract,
    entry: dict[str, Any],
    args: list[Any],
    wallet_view: WalletView,
    errors: list[str],
    method_key: str,
) -> None:
    """
    Render and submit a state-changing contract call through the browser wallet.
    """

    state_key = f"send-result:{method_key}"
    state = st.session_state.setdefault(state_key, {"status": None, "message": None, "payload": None})
    tx_params, tx_errors = _transaction_overrides(method_key)
    all_errors = [*errors, *tx_errors]
    if tx_errors:
        st.error("; ".join(tx_errors))

    if not wallet_view.connected:
        st.info("Connect your wallet to send transactions.")
    elif wallet_view.chain_id != chain_id:
        st.info(f"Switch your wallet to chain `{chain_id}` to send transactions.")
    elif wallet_view.selected_account is None:
        st.info("Select a wallet account in the sidebar to send transactions.")

    request_key = f"eth_sendTransaction:{chain_id}:{contract_address}:{method_key}"
    disabled = bool(all_errors) or not wallet_view.can_transact(expected_chain_id=chain_id)
    if st.button("Send transaction", key=f"send:{method_key}", disabled=disabled):
        try:
            data_hex = getattr(contract.functions, entry["name"])(*args)._encode_transaction_data()
        except Exception as exc:
            state["status"] = "error"
            state["message"] = str(exc)
            state["payload"] = None
        else:
            payload = {
                "from": Web3.to_checksum_address(wallet_view.selected_account),
                "to": Web3.to_checksum_address(contract.address),
                "data": data_hex,
                **tx_params,
            }
            state["payload"] = json.dumps(payload, indent=2)

            status, result = wallet_view.wallet.request("eth_sendTransaction", [payload], key=request_key)
            if status == "pending":
                state["status"] = "pending"
                state["message"] = "Transaction is pending wallet confirmation."
            elif status == "success":
                state["status"] = "success"
                state["message"] = f"Transaction hash: {result}"
                wallet_view.wallet.forget(request_key)
            else:
                state["status"] = "error"
                state["message"] = str(result)
                wallet_view.wallet.forget(request_key)

    if state["status"] == "pending" and state["message"]:
        st.info(state["message"])
    elif state["status"] == "success" and state["message"]:
        st.success(state["message"])
    elif state["status"] == "error" and state["message"]:
        st.error(state["message"])
    if state["payload"]:
        st.code(state["payload"], language="json")


def _transaction_overrides(method_key: str) -> tuple[dict[str, str], list[str]]:
    """
    Render optional transaction override fields and return parsed RPC payload values.
    """

    tx_params: dict[str, str] = {}
    errors: list[str] = []
    with st.expander("Transaction options"):
        value = st.text_input("Value (wei)", value="0", key=f"value:{method_key}")
        gas = st.text_input("Gas", value="", key=f"gas:{method_key}")
        max_fee = st.text_input("Max fee per gas", value="", key=f"maxfee:{method_key}")
        max_priority = st.text_input("Max priority fee per gas", value="", key=f"priority:{method_key}")

        for label, raw_value, field in [
            ("value", value, "value"),
            ("gas", gas, "gas"),
            ("max fee per gas", max_fee, "maxFeePerGas"),
            ("max priority fee per gas", max_priority, "maxPriorityFeePerGas"),
        ]:
            parsed, error = _parse_optional_uint(raw_value)
            if error:
                errors.append(f"{label}: {error}")
            elif parsed is not None:
                tx_params[field] = hex(parsed)
    return tx_params, errors


def _event_storage_key(event_signature: str) -> str:
    """
    Compute the worker/server storage key for one canonical event signature.
    """

    return "0x" + Web3.keccak(text=event_signature).hex()


def _function_selector(method_key: str) -> str:
    """
    Compute the 4-byte function selector for one canonical method key.
    """

    return "0x" + Web3.keccak(text=method_key).hex()[:8]


def _parse_optional_uint(raw_value: str) -> tuple[int | None, str | None]:
    """
    Parse one optional decimal integer field used in transaction overrides.
    """

    value = raw_value.strip()
    if not value:
        return None, None
    try:
        parsed = int(value, 10)
    except ValueError:
        return None, "expected non-negative integer"
    if parsed < 0:
        return None, "expected non-negative integer"
    return parsed, None


def _json_safe(value: Any) -> Any:
    """
    Convert Web3 return values into JSON-serializable structures for display.
    """

    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, bytes):
        return "0x" + value.hex()
    if hasattr(value, "hex") and callable(value.hex):
        try:
            return value.hex()
        except TypeError:
            return str(value)
    return value


def _render_warnings(warnings: list[str]) -> None:
    """
    Render loader warnings when present.
    """

    if warnings:
        with st.expander("Load warnings"):
            for warning in warnings:
                st.warning(warning)
