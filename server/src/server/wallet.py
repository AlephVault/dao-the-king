from __future__ import annotations
from dataclasses import dataclass
from typing import Any
import streamlit as st
from streamlit_browser_web3 import wallet_get
from web3 import Web3


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
        return [Web3.to_checksum_address(a) for a in self.wallet.accounts]

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
    if wallet.status == "not-available":
        st.warning("No browser wallet provider is available.")
        return

    st.write(f"Status: {f'Connected (chain id: `{wallet_view.chain_id}`)'
                        if wallet_view.connected else
                        'Disconnected'}")
    if wallet_view.connected:
        selected = st.selectbox(
            "Account",
            wallet_view.accounts,
            index=wallet_view.accounts.index(wallet_view.selected_account) if wallet_view.selected_account in wallet_view.accounts else 0,
            key="wallet:selected_account:select",
        )
        st.session_state["wallet:selected_account"] = selected
        wallet_view.selected_account = selected

        if st.button("Disconnect wallet", key="wallet-disconnect", disabled=wallet.busy):
            wallet.disconnect()
    else:
        if st.button("Connect wallet", key="wallet-connect", disabled=wallet.busy):
            wallet.connect()

    if wallet.last_error:
        st.error(wallet.last_error)


def render_chain_wallet_prompt(wallet_view: WalletView, *, expected_chain_id: int) -> None:
    """
    Render the chain-selection/connect/disconnect prompt on chain-aware pages.
    """

    wallet = wallet_view.wallet
    if wallet.status == "not-available":
        st.error("No wallet is available in your browser.")
        return

    if not wallet_view.connected:
        st.warning("Connect your wallet to use this chain directly from the browser.")
        if st.button(
            "Connect wallet",
            key=f"wallet-prompt-connect:{expected_chain_id}",
            disabled=wallet.busy,
            use_container_width=True,
        ):
            wallet.connect()
        return

    if wallet_view.chain_id != expected_chain_id:
        st.warning(f"Wallet is on chain `{wallet_view.chain_id}`. Switch it to `{expected_chain_id}`.")
        request_key = f"wallet_switchEthereumChain:{expected_chain_id}"
        request_status = wallet.get_request_status(request_key)
        if st.button(
            f"Switch to chain {expected_chain_id}",
            key=f"wallet-switch-button:{expected_chain_id}",
            disabled=wallet.busy,
            use_container_width=True,
        ):
            status, result = wallet.request(
                "wallet_switchEthereumChain",
                [{"chainId": hex(expected_chain_id)}],
                key=request_key,
            )
            if status == "error":
                wallet.forget(request_key)
                st.error(f"Switch failed: {result}")
                return
        elif request_status:
            status_, result = request_status
            match status_:
                case "pending":
                    st.info(f"Waiting for your wallet to switch to chain `{expected_chain_id}`.")
                case "success":
                    wallet.forget(request_key)
                    st.rerun()
                case "error":
                    st.error(f"An error occurred while switching chains: {result}")
                    wallet.forget(request_key)
        return
