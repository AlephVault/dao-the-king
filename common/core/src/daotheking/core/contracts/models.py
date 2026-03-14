from __future__ import annotations
from enum import StrEnum
from pathlib import Path
from typing import Any
from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, field_validator, model_validator


class RetrievalSampling(BaseModel):
    """
    The specification for retrieval sampling configuration.
    """

    probability: float
    min: int = 0

    @field_validator("probability")
    @classmethod
    def validate_probability(cls, value: float) -> float:
        if value <= 0 or value >= 1:
            raise ValueError("probability must satisfy 0 < x < 1")
        return value

    @field_validator("min")
    @classmethod
    def validate_min(cls, value: int) -> int:
        if value < 0:
            raise ValueError("min must be >= 0")
        return value


RetrieveRule = bool | RetrievalSampling


class ContractRetrieveSpec(BaseModel):
    """
    The specification for the retrieval sampling
    configuration for transactions and events.
    """

    transactions: RetrieveRule = False
    events: bool | dict[str, RetrieveRule] = False


class ContractEntry(BaseModel):
    """
    The specification for a contract entry. It
    includes the ABI file, the address, and the
    specifications for what to retrieve.
    """

    address: str
    abi: str | None = None
    retrieve: ContractRetrieveSpec = Field(default_factory=ContractRetrieveSpec)

    @field_validator("abi")
    @classmethod
    def normalize_abi(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return str(Path(value))


class ChainEntry(BaseModel):
    """
    The specification for the supported chains
    and the contract entries.
    """

    name: str
    rpc: AnyHttpUrl
    contracts: list[ContractEntry] = Field(default_factory=list)

    @field_validator("rpc")
    @classmethod
    def validate_http_scheme(cls, value: AnyHttpUrl) -> AnyHttpUrl:
        if value.scheme not in {"http", "https"}:
            raise ValueError("rpc must be an http or https URL")
        return value


class ContractsFile(BaseModel):
    """
    The contents for a contracts configuration file.
    """

    model_config = ConfigDict(extra="forbid")
    chains: dict[int, ChainEntry]

    @model_validator(mode="before")
    @classmethod
    def coerce_root(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            raise ValueError("contracts file must be a JSON object")
        if "chains" in value:
            return value

        chains: dict[int, Any] = {}
        for key, item in value.items():
            try:
                chain_id = int(key)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"invalid chain id key: {key!r}") from exc
            chains[chain_id] = item
        return {"chains": chains}


class ContractLoadError(StrEnum):
    COULD_NOT_OPEN_CONTRACTS_FILE = "could_not_open_contracts_file"
    INVALID_CONTRACTS_FILE_FORMAT = "invalid_contracts_file_format"
    INVALID_ADDRESS = "invalid_address"
    INVALID_ABI_FILE = "invalid_abi_file"
    NO_API_KEY_FOR_VERIFICATION = "no_api_key_for_verification"
    ETHERSCAN_VERIFICATION_ERROR = "etherscan_verification_error"
    CONTRACT_NOT_VERIFIED = "contract_not_verified"
