// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";
import {IERC721} from "@openzeppelin/contracts/token/ERC721/IERC721.sol";
import {ERC721Holder} from "@openzeppelin/contracts/token/ERC721/utils/ERC721Holder.sol";

contract SampleERC721Receiver is ERC721Holder, Ownable {
    constructor(address initialOwner) Ownable(initialOwner) {}

    function deposit(address token, uint256 tokenId) external {
        IERC721(token).safeTransferFrom(msg.sender, address(this), tokenId);
    }

    function withdraw(address token, address to, uint256 tokenId) external onlyOwner {
        IERC721(token).safeTransferFrom(address(this), to, tokenId);
    }
}
