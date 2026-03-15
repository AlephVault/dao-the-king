from __future__ import annotations
import streamlit as st
from server.data import load_server_data
from server.navigation import current_chain_id, render_contracts_sidebar
from server.pages import render_chain_page, render_contract_page, render_main_page, render_method_page
from server.settings import ServerSettings
from server.wallet import get_wallet_view, render_wallet_sidebar


def main() -> None:
    """
    Run the Streamlit server and dispatch to the active page.
    """

    st.set_page_config(layout="wide", page_title="Dao The King")
    settings = ServerSettings.from_env()
    data = load_server_data(settings)
    wallet_view = get_wallet_view()

    with st.sidebar:
        render_wallet_sidebar(wallet_view)
        st.divider()
        render_contracts_sidebar(data)

    st.title("Dao The King")
    chain_id = current_chain_id()
    contract_address = st.query_params.get("contract")
    method_key = st.query_params.get("method")

    if chain_id is None:
        render_main_page(data)
        return

    if chain_id not in data.contracts:
        st.error(f"Unknown chain `{chain_id}`.")
        return

    if not contract_address:
        render_chain_page(data, wallet_view, chain_id)
        return

    if contract_address not in data.contracts[chain_id]:
        st.error(f"Unknown contract `{contract_address}` on chain `{chain_id}`.")
        return

    result = data.contracts[chain_id][contract_address]
    if not method_key:
        render_contract_page(data, wallet_view, chain_id, contract_address, result)
        return

    render_method_page(data, wallet_view, chain_id, contract_address, result, method_key)


if __name__ == "__main__":
    main()
