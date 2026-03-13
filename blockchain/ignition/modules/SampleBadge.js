import { buildModule } from "@nomicfoundation/hardhat-ignition/modules";

export default buildModule("SampleBadgeModule", (m) => {
  const owner = m.getAccount(0);
  const badge = m.contract("SampleBadge", [
    "Sample Badge",
    "BADGE",
    owner,
    "ipfs://sample-badge/1.json",
  ]);

  return { badge };
});
