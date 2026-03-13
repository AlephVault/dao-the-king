import { buildModule } from "@nomicfoundation/hardhat-ignition/modules";

export default buildModule("SampleERC1155Module", (m) => {
  const owner = m.getAccount(0);
  const token = m.contract("SampleERC1155", [
    owner,
    "ipfs://sample-erc1155/{id}.json",
  ]);

  return { token };
});
