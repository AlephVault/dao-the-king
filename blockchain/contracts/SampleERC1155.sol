// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";
import {ERC1155} from "@openzeppelin/contracts/token/ERC1155/ERC1155.sol";

contract SampleERC1155 is ERC1155, Ownable {
    uint256 public constant GOLD_BADGE = 1;
    uint256 public constant SILVER_BADGE = 2;

    constructor(address initialOwner, string memory baseUri) ERC1155(baseUri) Ownable(initialOwner) {
        _mint(initialOwner, GOLD_BADGE, 100, "");
        _mint(initialOwner, SILVER_BADGE, 250, "");
    }

    function mint(address to, uint256 id, uint256 amount, bytes memory data) external onlyOwner {
        _mint(to, id, amount, data);
    }

    function mintBatch(
        address to,
        uint256[] memory ids,
        uint256[] memory amounts,
        bytes memory data
    ) external onlyOwner {
        _mintBatch(to, ids, amounts, data);
    }

    function supportsInterface(bytes4 interfaceId) public view virtual override returns (bool) {
        return super.supportsInterface(interfaceId);
    }
}
