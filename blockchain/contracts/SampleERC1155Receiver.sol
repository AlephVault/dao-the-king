// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";
import {IERC1155} from "@openzeppelin/contracts/token/ERC1155/IERC1155.sol";
import {ERC1155Holder} from "@openzeppelin/contracts/token/ERC1155/utils/ERC1155Holder.sol";

contract SampleERC1155Receiver is ERC1155Holder, Ownable {
    constructor(address initialOwner) Ownable(initialOwner) {}

    function deposit(
        address token,
        uint256 id,
        uint256 amount,
        bytes memory data
    ) external {
        IERC1155(token).safeTransferFrom(msg.sender, address(this), id, amount, data);
    }

    function depositBatch(
        address token,
        uint256[] memory ids,
        uint256[] memory amounts,
        bytes memory data
    ) external {
        IERC1155(token).safeBatchTransferFrom(msg.sender, address(this), ids, amounts, data);
    }

    function withdraw(
        address token,
        address to,
        uint256 id,
        uint256 amount,
        bytes memory data
    ) external onlyOwner {
        IERC1155(token).safeTransferFrom(address(this), to, id, amount, data);
    }

    function withdrawBatch(
        address token,
        address to,
        uint256[] memory ids,
        uint256[] memory amounts,
        bytes memory data
    ) external onlyOwner {
        IERC1155(token).safeBatchTransferFrom(address(this), to, ids, amounts, data);
    }

    function supportsInterface(bytes4 interfaceId) public view virtual override returns (bool) {
        return super.supportsInterface(interfaceId);
    }
}
