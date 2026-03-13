# blockchain

Temporary Hardhat workspace for local contract development and ABI generation.

## Deploying

1. In a terminal run and keep: `npx hardhat node`.
2. Remove the ignition/deployments/chain-31337` directory, if any.
3. Run this command to deploy: `ls ignition/modules/ | xargs -I xxx npx hardhat ignition deploy ignition/modules/xxx --network localhost`.
