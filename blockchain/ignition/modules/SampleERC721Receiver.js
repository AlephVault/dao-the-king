import { buildModule } from "@nomicfoundation/hardhat-ignition/modules";

export default buildModule("SampleERC721ReceiverModule", (m) => {
  const owner = m.getAccount(0);
  const receiver = m.contract("SampleERC721Receiver", [owner]);

  return { receiver };
});
