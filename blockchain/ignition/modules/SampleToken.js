import { buildModule } from "@nomicfoundation/hardhat-ignition/modules";

export default buildModule("SampleTokenModule", (m) => {
  const token = m.contract("SampleToken");
  return { token };
});
