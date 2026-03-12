from __future__ import annotations
import json
from pathlib import Path
from typing import Any


class AbiFileCache:
    """
    The cache for the ABI of each contract. If many
    contracts refer the same ABI, then these contracts
    will hold the same ABI object in the end.
    """

    def __init__(self) -> None:
        self._cache: dict[Path, list[dict[str, Any]]] = {}

    def load(self, path: str | Path) -> list[dict[str, Any]]:
        """
        Loads the ABI from a file. If there's an error, then
        it forces a failure. If the file was already loaded
        then it is used directly.
        :param path: The path of the file to load.
        :return: The ABI object (not validated, however).
        """

        resolved = Path(path).expanduser().resolve()
        if resolved in self._cache:
            return self._cache[resolved]

        with resolved.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)

        if not isinstance(payload, list):
            raise ValueError("ABI file must contain a JSON list")
        self._cache[resolved] = payload
        return payload
