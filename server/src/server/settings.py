from __future__ import annotations
import os
from dataclasses import dataclass


@dataclass(slots=True)
class ServerSettings:
    """
    The settings for the server. Includes paging configuration,
    API keys, server connection and configuration.
    """

    mongodb_uri: str
    mongodb_database: str
    contracts_file_path: str
    etherscan_api_key: str | None
    transactions_page_size: int = 20
    events_page_size: int = 20

    @classmethod
    def from_env(cls) -> "ServerSettings":
        contracts_file_path = os.getenv("DTK_CONTRACTS_FILE")
        mongodb_uri = os.getenv("DTK_MONGODB_URI")
        mongodb_database = os.getenv("DTK_MONGODB_DATABASE", "daotheking")
        if not contracts_file_path:
            raise ValueError("DTK_CONTRACTS_FILE is required")
        if not mongodb_uri:
            raise ValueError("DTK_MONGODB_URI is required")
        return cls(
            mongodb_uri=mongodb_uri,
            mongodb_database=mongodb_database,
            contracts_file_path=contracts_file_path,
            etherscan_api_key=os.getenv("ETHERSCAN_API_KEY"),
            transactions_page_size=int(os.getenv("DTK_SERVER_TRANSACTIONS_PAGE_SIZE", "20")),
            events_page_size=int(os.getenv("DTK_SERVER_EVENTS_PAGE_SIZE", "20")),
        )
