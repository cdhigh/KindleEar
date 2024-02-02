from abc import ABCMeta, abstractmethod
from typing import Any


class FieldABC(metaclass=ABCMeta):
    @property
    def default(self):
        raise NotImplementedError  # pragma: no cover

    @abstractmethod
    def loads(self, serialized_value: Any) -> Any:
        raise NotImplementedError  # pragma: no cover

    @abstractmethod
    def dumps(self, value: Any) -> Any:
        raise NotImplementedError  # pragma: no cover

    @abstractmethod
    def check_type(self, value) -> bool:
        raise NotImplementedError  # pragma: no cover

    @abstractmethod
    def __eq__(self, other: Any):
        raise NotImplementedError  # pragma: no cover

    @abstractmethod
    def __lt__(self, other: Any):
        raise NotImplementedError  # pragma: no cover

    @abstractmethod
    def __gt__(self, other: Any):
        raise NotImplementedError  # pragma: no cover

    @abstractmethod
    def __le__(self, other: Any):
        raise NotImplementedError  # pragma: no cover

    @abstractmethod
    def __ge__(self, other: Any):
        raise NotImplementedError  # pragma: no cover

    @abstractmethod
    def __repr__(self):
        raise NotImplementedError  # pragma: no cover
