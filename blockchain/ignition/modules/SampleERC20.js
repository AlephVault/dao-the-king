import { buildModule } from "@nomicfoundation/hardhat-ignition/modules";

const INITIAL_SUPPLY = 1_000_000n * 10n ** 18n;

export default buildModule("SampleERC20Module", (m) => {
  const owner = m.getAccount(0);
  const token = m.contract("SampleERC20", ["Sample ERC20", "S20", owner, INITIAL_SUPPLY]);

  return { token };
});
