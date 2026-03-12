# daotheking-core

Shared Python primitives for the Dao The King stack.

## Included

- Contract configuration parsing from `DTK_CONTRACTS_FILE`
- ABI resolution from local files or Etherscan V2
- Web3 contract instantiation
- Standard and badge detection with cache integration
- Storage abstractions with in-memory and MongoDB backends

## Environment

- `DTK_CONTRACTS_FILE`: path to the contracts JSON file
- `ETHERSCAN_API_KEY`: optional Etherscan V2 API key

## Sample Configuration

See `examples/contracts.sample.json`.
