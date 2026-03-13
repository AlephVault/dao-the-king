# daotheking-core

Shared Python primitives for the Dao The King stack.

## Included

- Contract configuration parsing from `DTK_CONTRACTS_FILE`
- ABI resolution from local files or Etherscan V2
- Web3 contract instantiation
- Standard and badge detection with cache integration
- Storage abstractions with in-memory and MongoDB backends

## Public API

The package exports these public names from `daotheking.core`:

- `load_contracts`
- `load_contracts_from_env`
- `detect_contract_badges`
- `ContractLoadResult`
- `ContractLoadError`
- `ContractBadgeResult`
- `StorageBackend`
- `InMemoryStorage`
- `MongoDBStorage`

### `load_contracts(...)`

Loads the configured contracts from a JSON file and returns:

- `({chain_id: {contract_address: ContractLoadResult}}, None)` on file-level success
- `({}, ContractLoadError....)` on file-level failure

Parameters:

- `contracts_file_path`: path to the JSON contracts file
- `etherscan_api_key`: optional Etherscan V2 key
- `storage`: optional storage backend used to cache computed badge metadata

Behavior:

- validates the contracts file with Pydantic
- requires HTTPS RPC URLs
- requires checksum addresses
- resolves ABI from file first, then Etherscan V2 if needed
- instantiates Web3 contracts
- computes badges and metadata, optionally caching them through the storage backend

Top-level file errors:

- `could_not_open_contracts_file`
- `invalid_contracts_file_format`

Per-contract errors stored inside `ContractLoadResult.error`:

- `invalid_address`
- `invalid_abi_file`
- `no_api_key_for_verification`
- `etherscan_verification_error`
- `contract_not_verified`

### `load_contracts_from_env(...)`

Same as `load_contracts(...)`, but reads:

- `DTK_CONTRACTS_FILE`
- `ETHERSCAN_API_KEY`

### `detect_contract_badges(contract)`

Inspects a Web3 contract instance and returns a `ContractBadgeResult`.

Behavior:

- matches supported badges against canonical ABI fragments from `known_abis.py`
- ignores parameter names when comparing ABI entries
- preserves tuple shape, outputs, event indexing, and mutability when matching
- checks `ERC1967` separately through the standard storage slots
- collects static metadata for supported standards where available

## Public Classes

### `ContractLoadResult`

Represents the result of loading one contract.

Fields:

- `contract`: the instantiated Web3 contract, or `None`
- `error`: a `ContractLoadError` value, or `None`
- `badges`: a `ContractBadgeResult`, or `None`
- `abi_source`: `"file"`, `"etherscan"`, or `None`
- `warnings`: non-fatal warnings collected while loading

### `ContractBadgeResult`

Represents detected badges and metadata for one contract.

Fields:

- `badges`: a dictionary keyed by badge name
- `metadata`: additional derived metadata about the ABI

Metadata keys:

- `functions`: sorted array of `(function_signature, abi_entry)`
- `events`: sorted array of `(event_signature, abi_entry)`
- `matched_badges`: sorted array of badge names that matched by ABI

Function signatures use a Solidity-like format such as:

```text
function transfer(address to, uint256 value) external returns (bool)
```

Event signatures use a Solidity-like format such as:

```text
event Transfer(address indexed from, address indexed to, uint256 value)
```

### `ContractLoadError`

String enum for contract loading failures.

Values:

- `COULD_NOT_OPEN_CONTRACTS_FILE`
- `INVALID_CONTRACTS_FILE_FORMAT`
- `INVALID_ADDRESS`
- `INVALID_ABI_FILE`
- `NO_API_KEY_FOR_VERIFICATION`
- `ETHERSCAN_VERIFICATION_ERROR`
- `CONTRACT_NOT_VERIFIED`

### `StorageBackend`

Abstract storage interface for contract cache, transactions, and events.

Required methods:

- `get_contract_cache(chain_id, contract_address)`
- `set_contract_cache(chain_id, contract_address, cache_object)`
- `clear_contract_cache(chain_id, contract_address)`
- `clear_chain_contract_cache(chain_id)`
- `clear_all_contracts_cache()`
- `get_contract_transactions_bookmark(chain_id, contract_address)`
- `set_contract_transactions_bookmark(chain_id, contract_address, last_block_number, last_transaction_index)`
- `store_transactions(chain_id, contract_address, transactions)`
- `get_transactions(chain_id, contract_address, offset, limit)`
- `get_transactions_count(chain_id, contract_address)`
- `get_contract_events_bookmark(chain_id, contract_address, event)`
- `set_contract_events_bookmark(chain_id, contract_address, event, block_number, transaction_index, log_index)`
- `store_events(chain_id, contract_address, events)`
- `get_events(chain_id, contract_address, event, offset, limit)`
- `get_events_count(chain_id, contract_address, event)`

The storage contract is intentionally snake_case only.

### `InMemoryStorage`

In-process implementation of `StorageBackend`.

Use it for:

- local development
- tests
- temporary cache behavior without persistence

### `MongoDBStorage`

MongoDB implementation of `StorageBackend`.

Construction:

- `MongoDBStorage(database)`
- `MongoDBStorage.from_uri(uri, database_name, **client_kwargs)`

Notes:

- `pymongo` is imported lazily and is not required unless this backend is used
- indexes are created automatically for cache lookups, bookmarks, upserts, and pagination

## Supported Badges

Badges currently matched from canonical ABI definitions:

- `ERC20`
- `ERC20Metadata`
- `ERC165`
- `ERC721`
- `ERC721Metadata`
- `ERC721TokenReceiver`
- `ERC1155`
- `ERC1155Metadata_URI`
- `ERC1155TokenReceiver`
- `ERC2612`
- `ERC3009`
- `ERC4337`
- `ERC4337Execute`

Special-case badge:

- `ERC1967`: detected from storage slots, not from `known_abis.py`

Current badge metadata enrichment:

- `ERC20Metadata`: `name`, `symbol`, `decimals`
- `ERC2612`: `domain_separator`
- `ERC721Metadata`: `name`, `symbol`
- `ERC1967`: populated `implementation`, `admin`, and `beacon` addresses when present

## Environment

- `DTK_CONTRACTS_FILE`: path to the contracts JSON file
- `ETHERSCAN_API_KEY`: optional Etherscan V2 API key

## Sample Configuration

See `examples/contracts.sample.json`.
