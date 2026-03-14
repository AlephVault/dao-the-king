from __future__ import annotations

import json
from math import ceil
from typing import Any
import streamlit as st
from web3 import Web3
from web3.contract import Contract
from server.abi import format_event_signature, format_function_signature, format_topic_signature, function_key
from server.data import ServerData, function_entries, load_server_data
from server.forms import render_parameter_input
from server.settings import ServerSettings
from server.wallet import render_wallet_panel


def main() -> None:
    """
    Run the Streamlit server entrypoint and dispatch to the active page.

    The page hierarchy is controlled through query parameters:
    chain -> contract -> method.
    """

    st.set_page_config(layout="wide", page_title="Dao The King")
    settings = ServerSettings.from_env()
    data = load_server_data(settings)

    st.title("Dao The King")
    chain_id = _query_int("chain")
    contract_address = st.query_params.get("contract")
    method_key = st.query_params.get("method")

    if chain_id is None:
        _render_chains_page(data.contracts)
        return
    if chain_id not in data.contracts:
        st.error(f"Unknown chain `{chain_id}`.")
        return

    chain_contracts = data.contracts[chain_id]
    if not contract_address:
        _render_contracts_page(chain_id, chain_contracts)
        return
    if contract_address not in chain_contracts:
        st.error(f"Unknown contract `{contract_address}` on chain `{chain_id}`.")
        return

    result = chain_contracts[contract_address]
    if result.contract is None or result.error is not None:
        st.error(f"Contract could not be loaded: {result.error}")
        if result.warnings:
            with st.expander("Load warnings"):
                for warning in result.warnings:
                    st.warning(warning)
        return

    wallet, wallet_error = render_wallet_panel(chain_id)
    if not method_key:
        _render_contract_page(
            data,
            chain_id,
            contract_address,
            result.contract,
            result.badges.badges if result.badges else {},
            result.warnings,
            wallet_error,
        )
        return

    _render_method_page(
        data,
        chain_id,
        contract_address,
        result.contract,
        method_key,
        result.warnings,
        wallet,
        wallet_error,
    )


def _render_chains_page(contracts: dict[int, dict[str, Any]]) -> None:
    """
    Render the top-level chain selection page.
    """

    st.subheader("Supported Chains")
    for chain_id in sorted(contracts):
        if st.button(f"Open chain {chain_id}", key=f"chain:{chain_id}"):
            _set_query_params(chain=chain_id)


def _render_contracts_page(chain_id: int, chain_contracts: dict[str, Any]) -> None:
    """
    Render the contract list for the selected chain.
    """

    st.subheader(f"Contracts on Chain {chain_id}")
    for address, result in sorted(chain_contracts.items()):
        label = address if result.error is None else f"{address} ({result.error})"
        if st.button(label, key=f"contract:{chain_id}:{address}", disabled=result.contract is None):
            _set_query_params(chain=chain_id, contract=address)


def _render_contract_page(
    data: ServerData,
    chain_id: int,
    contract_address: str,
    contract: Contract,
    badges: dict[str, Any],
    warnings: list[str],
    wallet_error: str | None,
) -> None:
    """
    Render the contract overview page with badges, methods, and stored activity.
    """

    st.subheader(f"Contract {contract_address}")
    if wallet_error:
        st.warning(wallet_error)
    if warnings:
        with st.expander("Load warnings"):
            for warning in warnings:
                st.warning(warning)

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

    st.write("Methods")
    for entry in functions:
        signature = format_function_signature(entry)
        if st.button(signature, key=f"method:{chain_id}:{contract_address}:{function_key(entry)}"):
            _set_query_params(chain=chain_id, contract=contract_address, method=function_key(entry))

    _render_transactions_section(data, chain_id, contract_address)
    _render_events_section(data, chain_id, contract_address, contract)


def _render_transactions_section(
    data: ServerData,
    chain_id: int,
    contract_address: str,
    method_key_filter: str | None = None,
) -> None:
    """
    Render the stored transactions section for a contract or one specific method.
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
        items = data.storage.get_transactions(
            chain_id,
            contract_address,
            offset,
            data.settings.transactions_page_size,
        )
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


def _render_events_section(data: ServerData, chain_id: int, contract_address: str, contract: Contract) -> None:
    """
    Render the stored event logs page for one contract.
    """

    st.subheader("Event Logs")
    event_entries = [entry for entry in contract.abi if entry.get("type") == "event"]
    if not event_entries:
        st.info("No events declared in ABI.")
        return

    options = {
        format_event_signature(entry): format_topic_signature(entry)
        for entry in event_entries
    }
    selected_label = st.selectbox(
        "Event",
        sorted(options),
        key=f"event-select:{chain_id}:{contract_address}",
    )
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


def _render_method_page(
    data: ServerData,
    chain_id: int,
    contract_address: str,
    contract: Contract,
    method_key: str,
    warnings: list[str],
    wallet: Any,
    wallet_error: str | None,
) -> None:
    """
    Render the method execution page for one ABI function.
    """

    entry = next((item for item in function_entries(contract) if function_key(item) == method_key), None)
    if entry is None:
        st.error(f"Unknown method `{method_key}`.")
        return

    st.subheader(format_function_signature(entry))
    if wallet_error:
        st.warning(wallet_error)
    if warnings:
        with st.expander("Load warnings"):
            for warning in warnings:
                st.warning(warning)

    args: list[Any] = []
    errors: list[str] = []
    for index, parameter in enumerate(entry.get("inputs", [])):
        value, error = render_parameter_input(parameter, f"method:{method_key}:{index}")
        args.append(value)
        if error:
            errors.append(f"{parameter.get('name') or index}: {error}")

    from_account = wallet.accounts[0] if wallet and wallet.accounts else None
    if wallet and wallet.accounts:
        from_account = st.selectbox("Account", wallet.accounts, key=f"account:{method_key}")

    if errors:
        st.error("; ".join(errors))

    state_mutability = entry.get("stateMutability")
    is_read_only = state_mutability in {"view", "pure"}

    if is_read_only:
        _render_call_action(contract, entry, args, from_account, errors, wallet_error, method_key)
    else:
        _render_send_action(
            chain_id,
            contract_address,
            contract,
            entry,
            args,
            from_account,
            errors,
            wallet,
            wallet_error,
            method_key,
        )

    _render_transactions_section(data, chain_id, contract_address, method_key_filter=method_key)


def _render_call_action(
    contract: Contract,
    entry: dict[str, Any],
    args: list[Any],
    from_account: str | None,
    errors: list[str],
    wallet_error: str | None,
    method_key: str,
) -> None:
    """
    Render and execute a read-only contract call.
    """

    if st.button("Execute call", key=f"call:{method_key}", disabled=bool(errors or wallet_error)):
        call_kwargs = {"from": from_account} if from_account else None
        try:
            result = getattr(contract.functions, entry["name"])(*args).call(call_kwargs)
        except Exception as exc:
            st.error(str(exc))
            return
        st.code(json.dumps(_json_safe(result), indent=2), language="json")


def _render_send_action(
    chain_id: int,
    contract_address: str,
    contract: Contract,
    entry: dict[str, Any],
    args: list[Any],
    from_account: str | None,
    errors: list[str],
    wallet: Any,
    wallet_error: str | None,
    method_key: str,
) -> None:
    """
    Render and submit a state-changing contract call through the browser wallet.
    """

    tx_params, tx_errors = _transaction_overrides(method_key)
    all_errors = [*errors, *tx_errors]
    if tx_errors:
        st.error("; ".join(tx_errors))

    request_key = f"eth_sendTransaction:{chain_id}:{contract_address}:{method_key}"
    if st.button("Send transaction", key=f"send:{method_key}", disabled=bool(all_errors or wallet_error)):
        try:
            data_hex = getattr(contract.functions, entry["name"])(*args)._encode_transaction_data()
        except Exception as exc:
            st.error(str(exc))
            return

        payload = {
            "from": from_account,
            "to": contract.address,
            "data": data_hex,
            **tx_params,
        }
        status, result = wallet.request("eth_sendTransaction", [payload], key=request_key)
        if status == "pending":
            st.info("Transaction is pending wallet confirmation.")
        elif status == "success":
            st.success(f"Transaction hash: {result}")
            wallet.forget(request_key)
        else:
            st.error(str(result))
            wallet.forget(request_key)
        st.code(json.dumps(payload, indent=2), language="json")


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


def _function_selector(method_key: str) -> str:
    """
    Compute the 4-byte function selector for one canonical method key.
    """

    return "0x" + Web3.keccak(text=method_key).hex()[:8]


def _event_storage_key(event_signature: str) -> str:
    """
    Compute the worker/server storage key for one canonical event signature.
    """

    return "0x" + Web3.keccak(text=event_signature).hex()


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


def _set_query_params(*, chain: int, contract: str | None = None, method: str | None = None) -> None:
    """
    Replace the current query parameters with a consistent navigation state.
    """

    st.query_params.clear()
    st.query_params["chain"] = str(chain)
    if contract is not None:
        st.query_params["contract"] = contract
    if method is not None:
        st.query_params["method"] = method
    st.rerun()


def _query_int(name: str) -> int | None:
    """
    Read one integer query parameter, returning `None` for missing or invalid values.
    """

    value = st.query_params.get(name)
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


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


if __name__ == "__main__":
    main()
