import { buildModule } from "@nomicfoundation/hardhat-ignition/modules";

export default buildModule("SampleERC1155ReceiverModule", (m) => {
  const owner = m.getAccount(0);
  const receiver = m.contract("SampleERC1155Receiver", [owner]);

  return { receiver };
});
