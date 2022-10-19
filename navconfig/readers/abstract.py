from typing import Any
from abc import ABC, abstractmethod


class AbstractReader(ABC):
    """AbstractReader.

    Description: Abstract class for External Readers.
    """
    @abstractmethod
    def get(self, key: str, default: Any = None) -> Any:
        pass

    @abstractmethod
    def exists(self, key: str) -> bool:
        pass

    @abstractmethod
    def close(self) -> None:
        pass

    @abstractmethod
    def set(self, key: str, value: Any, timeout: int = None) -> None:
        pass

    @abstractmethod
    def delete(self, key: str) -> bool:
        pass
