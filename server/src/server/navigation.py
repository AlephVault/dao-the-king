from __future__ import annotations

from urllib.parse import urlencode

import streamlit as st

from .data import ServerData


def app_url(*, chain_id: int | None = None, contract: str | None = None, method: str | None = None) -> str:
    """
    Build an in-app URL with the expected query parameter names.
    """

    params: list[tuple[str, str]] = []
    if chain_id is not None:
        params.append(("chain_id", str(chain_id)))
    if contract is not None:
        params.append(("contract", contract))
    if method is not None:
        params.append(("method", method))
    return f"?{urlencode(params)}" if params else "?"


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
    Render one breadcrumb row using in-app markdown links.
    """

    st.markdown(" > ".join(f"[{label}]({url})" for label, url in items))


def render_contracts_sidebar(data: ServerData) -> None:
    """
    Render the chain/contract navigation tree in the sidebar.
    """

    lines = [f"- [Supported Chains]({app_url()})"]
    for chain_id in sorted(data.contracts):
        lines.append(f"- [{chain_label(data, chain_id)}]({app_url(chain_id=chain_id)})")
        for address in sorted(data.contracts[chain_id]):
            lines.append(
                f"  - [{address}]({app_url(chain_id=chain_id, contract=address)})"
            )
    st.markdown("\n".join(lines))
