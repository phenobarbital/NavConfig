from typing import Any
from abc import ABC, abstractmethod


class AbstractReader(ABC):
    """AbstractReader.

    Description: Abstract class for External Readers.
    """
    @abstractmethod
    async def get(self, key: str, default: Any = None) -> Any:
        pass

    @abstractmethod
    async def exists(self, key: str) -> bool:
        pass

    @abstractmethod
    async def close(self) -> None:
        pass

    @abstractmethod
    async def set(self, key: str, value: Any, timeout: int = None) -> None:
        pass

    @abstractmethod
    async def delete(self, key: str) -> bool:
        pass
