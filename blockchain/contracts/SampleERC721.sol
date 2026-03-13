// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";
import {ERC721} from "@openzeppelin/contracts/token/ERC721/ERC721.sol";
import {ERC721URIStorage} from "@openzeppelin/contracts/token/ERC721/extensions/ERC721URIStorage.sol";

contract SampleERC721 is ERC721URIStorage, Ownable {
    uint256 public nextTokenId = 1;

    constructor(
        string memory name_,
        string memory symbol_,
        address initialOwner,
        string memory initialTokenUri
    ) ERC721(name_, symbol_) Ownable(initialOwner) {
        _safeMint(initialOwner, nextTokenId);
        _setTokenURI(nextTokenId, initialTokenUri);
        nextTokenId += 1;
    }

    function mint(address to, string memory tokenUri) external onlyOwner returns (uint256 tokenId) {
        tokenId = nextTokenId;
        _safeMint(to, tokenId);
        _setTokenURI(tokenId, tokenUri);
        nextTokenId += 1;
    }

    function supportsInterface(bytes4 interfaceId) public view virtual override returns (bool) {
        return super.supportsInterface(interfaceId);
    }
}
