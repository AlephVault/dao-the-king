# daotheking-worker

Background worker for Dao The King.

## What It Does

The worker:

- loads the configured contracts through `daotheking-core`
- computes and caches contract badges in MongoDB
- retrieves transactions for contracts through Etherscan V2
- decodes calldata with the contract ABI when possible
- retrieves event logs through the configured RPC endpoint
- stores transaction and event bookmarks in MongoDB
- runs continuously unless configured for one-shot mode

## Dependencies

The worker package depends on:

- `daotheking-core`
- `pymongo`

`web3` support comes through `daotheking-core`.

## Environment Variables

- `DTK_CONTRACTS_FILE`: required path to the contracts JSON file
- `DTK_MONGODB_URI`: required MongoDB connection URI
- `DTK_MONGODB_DATABASE`: MongoDB database name, default `daotheking`
- `ETHERSCAN_API_KEY`: optional, but required if transaction retrieval or ABI fallback through Etherscan is needed
- `DTK_WORKER_POLL_INTERVAL`: seconds between loop iterations, default `15`
- `DTK_WORKER_BLOCK_BATCH_SIZE`: number of blocks per RPC log batch, default `2000`
- `DTK_WORKER_ETHERSCAN_PAGE_SIZE`: Etherscan page size for transaction polling, default `100`
- `DTK_WORKER_ETHERSCAN_TIMEOUT`: Etherscan request timeout in seconds, default `15`
- `DTK_WORKER_ONCE`: if true-like, run one iteration and exit

## Installation

From the monorepo:

```bash
pip install -e common/core
pip install -e worker
```

## Usage

Run the worker directly:

```bash
export DTK_CONTRACTS_FILE=/absolute/path/to/contracts.json
export DTK_MONGODB_URI=mongodb://localhost:27017
export DTK_MONGODB_DATABASE=daotheking
export ETHERSCAN_API_KEY=...
daotheking-worker
```

Run one pass only:

```bash
DTK_WORKER_ONCE=1 daotheking-worker
```

## Retrieval Behavior

### Transactions

If `retrieve.transactions` is enabled for a contract, the worker:

- fetches transactions from Etherscan for the contract address in ascending order
- resumes from the saved `(block_number, transaction_index)` bookmark
- stores the raw transaction payload
- decodes calldata into `decoded_input` when ABI decoding succeeds
- fetches and stores the transaction receipt in `receipt`

Sampling rules are respected like this:

- `true`: store all transactions
- `{ probability, min }`: store the first `min` deterministically, then sample subsequent transactions with the given probability

### Events

If `retrieve.events` is enabled for a contract, the worker:

- resolves the requested event set from the ABI
- accepts simple names like `Transfer`
- also accepts full signatures like `Transfer(address,address,uint256)` and Solidity-style event forms
- fetches logs through the chain RPC with `eth_getLogs`
- resumes from the saved `(block_number, transaction_index, log_index)` bookmark
- decodes log arguments using the ABI

Sampling rules behave the same as for transactions.

## Docker Compose

The included `docker-compose.yml` starts:

- `mongodb`
- `worker`

Expected local layout for compose:

```text
worker/
  docker-compose.yml
  contracts/
    contracts.json
```

Start it with:

```bash
cd worker
docker compose up --build
```

## Storage Fields

Stored transactions use snake_case fields like:

- `block_number`
- `transaction_index`
- `decoded_input`
- `receipt`

Stored events use snake_case fields like:

- `block_number`
- `transaction_index`
- `log_index`
- `transaction_hash`
- `args`
- `log`
