from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import streamlit as st
from streamlit_browser_web3 import wallet_get


@dataclass(slots=True)
class WalletView:
    """
    Snapshot of the browser wallet state plus the selected account.
    """

    wallet: Any
    selected_account: str | None

    @property
    def connected(self) -> bool:
        return self.wallet.status == "connected"

    @property
    def chain_id(self) -> int | None:
        return self.wallet.chain_id

    @property
    def accounts(self) -> list[str]:
        return list(self.wallet.accounts)

    def can_transact(self, *, expected_chain_id: int) -> bool:
        return self.connected and self.chain_id == expected_chain_id and self.selected_account is not None


def get_wallet_view() -> WalletView:
    """
    Resolve the browser wallet and synchronize the selected account state.
    """

    wallet = wallet_get()
    if wallet.status == "connected" and wallet.last_error:
        # Clear stale component errors after the wallet reaches a healthy
        # connected state so the sidebar matches the main-page status.
        wallet._state["last_error"] = None
    selected_account_key = "wallet:selected_account"
    selected_account = st.session_state.get(selected_account_key)
    if wallet.accounts:
        if selected_account not in wallet.accounts:
            selected_account = wallet.accounts[0]
            st.session_state[selected_account_key] = selected_account
    else:
        selected_account = None
        st.session_state.pop(selected_account_key, None)
    return WalletView(wallet=wallet, selected_account=selected_account)


def render_wallet_sidebar(wallet_view: WalletView) -> None:
    """
    Render the wallet controls in the sidebar.
    """

    wallet = wallet_view.wallet
    st.subheader("Wallet")
    st.write(f"Status: {'Connected' if wallet_view.connected else 'Disconnected'}")
    if wallet.last_error:
        st.error(wallet.last_error)

    if wallet.status == "not-available":
        st.warning("No browser wallet provider is available.")
        return

    if wallet_view.connected:
        if st.button("Disconnect wallet", key="wallet-disconnect", disabled=wallet.busy):
            wallet.disconnect()
        if wallet_view.chain_id is not None:
            st.write(f"Current chain: `{wallet_view.chain_id}`")
        selected = st.selectbox(
            "Account",
            wallet_view.accounts,
            index=wallet_view.accounts.index(wallet_view.selected_account) if wallet_view.selected_account in wallet_view.accounts else 0,
            key="wallet:selected_account:select",
        )
        st.session_state["wallet:selected_account"] = selected
        wallet_view.selected_account = selected
    else:
        if st.button("Connect wallet", key="wallet-connect", disabled=wallet.busy):
            wallet.connect()


def render_chain_wallet_prompt(wallet_view: WalletView, *, expected_chain_id: int) -> None:
    """
    Render the chain-selection/connect/disconnect prompt on chain-aware pages.
    """

    st.subheader("Wallet for This Chain")
    if wallet_view.wallet.status == "not-available":
        st.warning("No browser wallet provider is available.")
        return

    if not wallet_view.connected:
        st.info("Connect your wallet to use this chain directly from the browser.")
        if st.button("Connect wallet", key=f"wallet-prompt-connect:{expected_chain_id}", disabled=wallet_view.wallet.busy):
            wallet_view.wallet.connect()
        return

    st.write(f"Wallet chain: `{wallet_view.chain_id}`")
    left, right = st.columns(2)
    with left:
        if st.button(
            f"Switch to chain {expected_chain_id}",
            key=f"wallet-switch-button:{expected_chain_id}",
            disabled=wallet_view.wallet.busy or wallet_view.chain_id == expected_chain_id,
            use_container_width=True,
        ):
            st.session_state[f"wallet:switch:{expected_chain_id}:requested"] = True
    with right:
        if st.button(
            "Disconnect wallet",
            key=f"wallet-prompt-disconnect:{expected_chain_id}",
            disabled=wallet_view.wallet.busy,
            use_container_width=True,
        ):
            wallet_view.wallet.disconnect()

    if wallet_view.chain_id == expected_chain_id:
        st.success(f"Wallet is already on chain `{expected_chain_id}`.")
        return

    switch_state_key = f"wallet:switch:{expected_chain_id}:requested"
    if not st.session_state.get(switch_state_key, False):
        st.warning(f"Wallet is on chain `{wallet_view.chain_id}`. Switch it to `{expected_chain_id}`.")
        return

    request_key = f"wallet_switchEthereumChain:{expected_chain_id}"
    status, result = wallet_view.wallet.request(
        "wallet_switchEthereumChain",
        [{"chainId": hex(expected_chain_id)}],
        key=request_key,
    )
    if status == "pending":
        st.info(f"Waiting for your wallet to switch to chain `{expected_chain_id}`.")
        return
    if status == "error":
        wallet_view.wallet.forget(request_key)
        st.session_state[switch_state_key] = False
        st.error(f"Switch failed: {result}")
        return
    wallet_view.wallet.forget(request_key)
    st.session_state[switch_state_key] = False
    st.rerun()
