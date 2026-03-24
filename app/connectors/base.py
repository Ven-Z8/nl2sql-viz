from abc import ABC, abstractmethod
from typing import Any


class BaseConnector(ABC):
    @abstractmethod
    async def connect(self) -> None: ...

    @abstractmethod
    async def disconnect(self) -> None: ...

    @abstractmethod
    async def execute_read(self, sql: str) -> list[dict[str, Any]]: ...

    @abstractmethod
    async def get_schema(self) -> dict[str, Any]: ...
