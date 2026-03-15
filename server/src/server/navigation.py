from __future__ import annotations

import streamlit as st

from .data import ServerData


def set_query_params(*, chain_id: int | None = None, contract: str | None = None, method: str | None = None) -> None:
    """
    Replace the current query parameters with the provided navigation state.
    """

    st.query_params.clear()
    if chain_id is not None:
        st.query_params["chain_id"] = str(chain_id)
    if contract is not None:
        st.query_params["contract"] = contract
    if method is not None:
        st.query_params["method"] = method
    st.rerun()


def query_int(name: str) -> int | None:
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


def current_chain_id() -> int | None:
    """
    Read the active chain query parameter, supporting the new and legacy names.
    """

    return query_int("chain_id") or query_int("chain")


def chain_label(data: ServerData, chain_id: int) -> str:
    """
    Render the human-readable label for one chain.
    """

    return f"{chain_id} - {data.chain_names.get(chain_id, 'Unknown')}"


def render_breadcrumbs(items: list[tuple[str, str]]) -> None:
    """
    Render one breadcrumb row using in-app buttons.
    """

    columns = st.columns(len(items))
    column_index = 0
    for index, (label, target) in enumerate(items):
        with columns[column_index]:
            if st.button("> " + label, key=f"breadcrumb:{index}:{target}", use_container_width=True):
                if target == "main":
                    set_query_params()
                elif target.startswith("chain:"):
                    set_query_params(chain_id=int(target.split(":", 1)[1]))
                elif target.startswith("contract:"):
                    chain_text, contract = target.split(":", 2)[1:]
                    set_query_params(chain_id=int(chain_text), contract=contract)
        column_index += 1


def render_contracts_sidebar(data: ServerData) -> None:
    """
    Render the chain/contract navigation tree in the sidebar.
    """

    st.subheader("Navigation")
    if st.button("Supported Chains", key="nav:main", use_container_width=True):
        set_query_params()
    for chain_id in sorted(data.contracts):
        with st.expander(chain_label(data, chain_id), expanded=False):
            if st.button(
                f"Open {chain_label(data, chain_id)}",
                key=f"nav:chain:{chain_id}",
                use_container_width=True,
            ):
                set_query_params(chain_id=chain_id)
            for address in sorted(data.contracts[chain_id]):
                if st.button(
                    address,
                    key=f"nav:contract:{chain_id}:{address}",
                    use_container_width=True,
                ):
                    set_query_params(chain_id=chain_id, contract=address)
