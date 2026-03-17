from __future__ import annotations
import hashlib
from collections.abc import Callable
import streamlit as st
from .abi import function_key
from .data import ServerData, contract_label, function_entries


PageRenderer = Callable[[int | None, str | None, str | None], None]
CHAIN_ICON = "⛓️"
CONTRACT_ICON = "📄"
METHOD_ICON = "➡️"


def set_query_params(*, chain_id: int | None = None, contract: str | None = None, method: str | None = None) -> None:
    """
    Navigate to the provided state, updating both the selected Streamlit page
    and the query parameters when a navigation page exists for that state.
    """

    query_params = _query_params_for(chain_id=chain_id, contract=contract, method=method)
    page = st.session_state.get("_contracts_navigation_pages", {}).get(
        _page_key(chain_id=chain_id, contract=contract, method=method)
    )
    if page is not None:
        st.switch_page(page, query_params=query_params or None)

    st.query_params.clear()
    for name, value in query_params.items():
        st.query_params[name] = value
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


def current_contract_address() -> str | None:
    """
    Read the active contract query parameter.
    """

    return st.query_params.get("contract")


def current_method_key() -> str | None:
    """
    Read the active method query parameter.
    """

    return st.query_params.get("method")


def chain_label(data: ServerData, chain_id: int) -> str:
    """
    Render the human-readable label for one chain.
    """

    return f"Chain {chain_id} - {data.chain_names.get(chain_id, 'Unknown')}"


def render_contracts_sidebar(data: ServerData, render_page: PageRenderer):
    """
    Render the dynamic navigation list in the sidebar and return the selected page.
    """

    pages = _build_navigation_pages(data, render_page)
    return st.navigation(pages, position="sidebar", expanded=True)


def _build_navigation_pages(data: ServerData, render_page: PageRenderer) -> list:
    """
    Build the sidebar page list, keeping every valid route registered so page
    switching never falls back to the default route mid-navigation.
    """

    chain_id = current_chain_id()
    contract = current_contract_address()
    method = current_method_key()

    visible_targets = {_page_key()}
    current_chain_valid = chain_id is not None and chain_id in data.contracts
    current_contract_valid = current_chain_valid and bool(contract) and contract in data.contracts[chain_id]

    if not current_chain_valid:
        visible_targets.update(_page_key(chain_id=available_chain_id) for available_chain_id in sorted(data.contracts))
    elif not current_contract_valid:
        visible_targets.add(_page_key())
        visible_targets.update(
            _page_key(chain_id=chain_id, contract=address)
            for address in sorted(data.contracts[chain_id])
        )
    elif method:
        visible_targets.update(
            {
                _page_key(),
                _page_key(chain_id=chain_id),
                _page_key(chain_id=chain_id, contract=contract),
            }
        )
    else:
        visible_targets.update(
            {
                _page_key(),
                _page_key(chain_id=chain_id),
            }
        )
        result = data.contracts[chain_id][contract]
        if result.contract is not None and result.error is None:
            visible_targets.update(
                _page_key(chain_id=chain_id, contract=contract, method=function_key(entry))
                for entry in function_entries(result.contract)
            )

    pages: list = [
        _navigation_page(
            render_page,
            title="Main",
            icon="🏠",
            visibility=_visibility_for(visible_targets, _page_key()),
        )
    ]

    for available_chain_id in sorted(data.contracts):
        pages.append(
            _navigation_page(
                render_page,
                title=chain_label(data, available_chain_id),
                chain_id=available_chain_id,
                icon=CHAIN_ICON,
                visibility=_visibility_for(visible_targets, _page_key(chain_id=available_chain_id)),
            )
        )
        for address, result in sorted(data.contracts[available_chain_id].items()):
            pages.append(
                _navigation_page(
                    render_page,
                    title=contract_label(data, available_chain_id, address),
                    chain_id=available_chain_id,
                    contract=address,
                    icon=CONTRACT_ICON,
                    visibility=_visibility_for(
                        visible_targets,
                        _page_key(chain_id=available_chain_id, contract=address),
                    ),
                )
            )
            if result.contract is None or result.error is not None:
                continue
            for entry in function_entries(result.contract):
                key = function_key(entry)
                pages.append(
                    _navigation_page(
                        render_page,
                        title=key,
                        chain_id=available_chain_id,
                        contract=address,
                        method=key,
                        icon=METHOD_ICON,
                        visibility=_visibility_for(
                            visible_targets,
                            _page_key(chain_id=available_chain_id, contract=address, method=key),
                        ),
                    )
                )

    return _register_navigation_pages(pages)


def _register_navigation_pages(pages: list) -> list:
    """
    Cache the current navigation pages so in-page buttons can switch to them.
    """

    st.session_state["_contracts_navigation_pages"] = {
        _page_key(
            chain_id=getattr(page, "_target_chain_id", None),
            contract=getattr(page, "_target_contract", None),
            method=getattr(page, "_target_method", None),
        ): page
        for page in pages
    }
    return pages


def _navigation_page(
    render_page: PageRenderer,
    *,
    title: str,
    chain_id: int | None = None,
    contract: str | None = None,
    method: str | None = None,
    icon: str | None = None,
    visibility: str = "visible",
):
    """
    Build one Streamlit navigation page for a specific navigation target.
    """

    def page_callable() -> None:
        _ensure_query_params(chain_id=chain_id, contract=contract, method=method)
        render_page(chain_id, contract, method)

    page = st.Page(
        page_callable,
        title=title,
        icon=icon,
        url_path=_page_url_path(chain_id=chain_id, contract=contract, method=method),
        default=chain_id is None and contract is None and method is None,
        visibility=visibility,
    )
    page._target_chain_id = chain_id
    page._target_contract = contract
    page._target_method = method
    return page


def _ensure_query_params(*, chain_id: int | None = None, contract: str | None = None, method: str | None = None) -> None:
    """
    Keep the query string synchronized with the active navigation page.
    """

    expected = _query_params_for(chain_id=chain_id, contract=contract, method=method)
    current = {
        "chain_id": st.query_params.get("chain_id"),
        "contract": st.query_params.get("contract"),
        "method": st.query_params.get("method"),
    }
    current = {name: value for name, value in current.items() if value is not None}
    if current == expected:
        return

    st.query_params.clear()
    for name, value in expected.items():
        st.query_params[name] = value
    st.rerun()


def _query_params_for(*, chain_id: int | None = None, contract: str | None = None, method: str | None = None) -> dict[str, str]:
    """
    Build the query params for one navigation target.
    """

    params: dict[str, str] = {}
    if chain_id is not None:
        params["chain_id"] = str(chain_id)
    if contract is not None:
        params["contract"] = contract
    if method is not None:
        params["method"] = method
    return params


def _page_key(*, chain_id: int | None = None, contract: str | None = None, method: str | None = None) -> str:
    """
    Build the internal key for one navigation target.
    """

    return f"{chain_id or ''}|{contract or ''}|{method or ''}"


def _page_url_path(*, chain_id: int | None = None, contract: str | None = None, method: str | None = None) -> str | None:
    """
    Build a stable sidebar URL path for one navigation target.
    """

    if chain_id is None and contract is None and method is None:
        return None
    digest = hashlib.md5(
        _page_key(chain_id=chain_id, contract=contract, method=method).encode("utf-8"),
        usedforsecurity=False,
    ).hexdigest()[:12]
    return f"nav-{digest}"


def _visibility_for(visible_targets: set[str], target: str) -> str:
    """
    Resolve one navigation target to a Streamlit page visibility value.
    """

    return "visible" if target in visible_targets else "hidden"
