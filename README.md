# dao-the-king

A monorepo for managing user-configured EVM smart contracts across worker and server applications.

## Layout

- `blockchain/`: temporary Hardhat workspace for contracts and local deployment.
- `common/core/`: shared Python package published as `daotheking-core`.
- `worker/`: background worker scaffold.
- `server/`: Streamlit management UI scaffold.

## Status

This repository currently includes the shared core package, storage abstractions, contract loading and badge detection, plus starter worker/server apps and a minimal Hardhat project.
