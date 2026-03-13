# daotheking-server

Streamlit management UI for Dao The King.

## What It Does

The server:

- loads the same configured contracts as the worker
- reads the worker MongoDB database through `MongoDBStorage`
- lists supported chains and contracts
- shows contract badges and proxy slot data
- filters callable methods by detected badge
- renders ABI-driven parameter forms
- executes read-only methods with `eth_call`
- executes state-changing methods through `streamlit-browser-web3`
- pages stored transactions and event logs from MongoDB

## Dependencies

- `daotheking-core`
- `pymongo`
- `streamlit`
- `streamlit-browser-web3`

## Environment Variables

- `DTK_CONTRACTS_FILE`: required path to the contracts JSON file
- `DTK_MONGODB_URI`: required MongoDB URI used by the worker
- `DTK_MONGODB_DATABASE`: MongoDB database name, default `daotheking`
- `ETHERSCAN_API_KEY`: optional, used for ABI fallback if needed
- `DTK_SERVER_TRANSACTIONS_PAGE_SIZE`: transactions page size, default `20`
- `DTK_SERVER_EVENTS_PAGE_SIZE`: events page size, default `20`

## Installation

From the monorepo:

```bash
pip install -e common/core
pip install -e server
```

## Usage

```bash
export DTK_CONTRACTS_FILE=/absolute/path/to/contracts.json
export DTK_MONGODB_URI=mongodb://localhost:27017
export DTK_MONGODB_DATABASE=daotheking
streamlit run server/src/daotheking/server/app.py
```

## Page Flow

The app exposes these page states through query parameters:

1. Chains page
2. Contracts page for a selected chain
3. Contract page for a selected chain and contract
4. Method page for a selected chain, contract, and method

## Wallet Behavior

The server uses `streamlit-browser-web3` and its `wallet_get()` handler.

Behavior:

- wallet state is rendered every rerun
- users are prompted to connect before executing methods
- users are prompted to switch to the selected chain before executing methods
- `eth_sendTransaction` is used for state-changing methods
- request progress is tracked across reruns with stable request keys

## MongoDB Connectivity

The server is designed to connect to the same MongoDB instance as the worker.

By default the compose files use a shared Docker network named `daotheking`, so:

- `worker/docker-compose.yml` starts `mongodb`
- `server/docker-compose.yml` connects to `mongodb` on that same network

## Docker Compose

Start the worker stack first:

```bash
cd worker
docker compose up --build
```

Then start the server stack:

```bash
cd server
docker compose up --build
```

## Current Scope

The current implementation supports:

- contract browsing
- badge filtering
- transaction and event pagination from MongoDB
- wallet connect / chain switch flow
- read-only calls and state-changing sends

What it does not yet do:

- richer presentation for stored transactions and logs beyond JSON views
- overloaded-method-specific transaction history beyond the decoded function name heuristic
