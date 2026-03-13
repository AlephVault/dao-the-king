import { buildModule } from "@nomicfoundation/hardhat-ignition/modules";

export default buildModule("SampleERC721Module", (m) => {
  const owner = m.getAccount(0);
  const token = m.contract("SampleERC721", [
    "Sample ERC721",
    "S721",
    owner,
    "ipfs://sample-erc721/1.json",
  ]);

  return { token };
});
