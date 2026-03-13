from __future__ import annotations
from typing import Any
import streamlit as st
from streamlit_browser_web3 import wallet_get


def render_wallet_panel(expected_chain_id: int) -> tuple[Any, str | None]:
    """
    Render the wallet sidebar and return the wallet handler plus any blocking error.

    The server only allows contract interaction after the browser wallet is
    connected and pointed at the currently selected chain. Chain switching is
    intentionally button-driven so the component request can survive Streamlit
    reruns until the wallet resolves it.
    """

    wallet = wallet_get()
    switch_request_key = f"switch:{expected_chain_id}"
    switch_state_key = f"wallet:switch:{expected_chain_id}:requested"
    with st.sidebar:
        st.subheader("Wallet")
        st.write(f"Status: `{wallet.status}`")
        if wallet.last_error:
            st.error(wallet.last_error)

        if wallet.status == "disconnected":
            if st.button("Connect wallet", key="wallet-connect"):
                wallet.connect()
        elif wallet.status == "connected":
            st.write(f"Accounts: {wallet.accounts}")
            st.write(f"Chain: {wallet.chain_id}")
            if st.button("Disconnect wallet", key="wallet-disconnect"):
                wallet.disconnect()

    if wallet.status == "not-available":
        return wallet, "No browser wallet provider is available."
    if wallet.status != "connected":
        return wallet, "Connect your wallet to continue."

    if wallet.chain_id != expected_chain_id:
        with st.sidebar:
            st.warning(f"Wallet is on chain `{wallet.chain_id}`. Expected `{expected_chain_id}`.")
            if st.button(f"Switch to chain {expected_chain_id}", key=f"wallet-switch:{expected_chain_id}"):
                st.session_state[switch_state_key] = True

        if not st.session_state.get(switch_state_key, False):
            return wallet, f"Switch your wallet to chain `{expected_chain_id}`."

        status, result = wallet.request(
            "wallet_switchEthereumChain",
            [{"chainId": hex(expected_chain_id)}],
            key=switch_request_key,
        )
        if status == "pending":
            return wallet, f"Waiting for your wallet to switch to chain `{expected_chain_id}`."
        if status == "error":
            wallet.forget(switch_request_key)
            st.session_state[switch_state_key] = False
            return wallet, f"Wallet is on chain `{wallet.chain_id}` and switch failed: {result}"
        wallet.forget(switch_request_key)
        st.session_state[switch_state_key] = False
        st.rerun()

    return wallet, None
