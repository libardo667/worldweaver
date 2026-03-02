"""Shared cache utilities."""

import time
from collections import OrderedDict
from typing import Any, Dict, Iterator, MutableMapping


class TTLCacheMap(MutableMapping[str, Any]):
    """Small LRU-ish cache map with TTL expiration and max-size bounds."""

    _MISSING = object()

    def __init__(self, max_size: int, ttl_seconds: int):
        self.max_size = max(1, int(max_size))
        self.ttl_seconds = max(1, int(ttl_seconds))
        self._data: "OrderedDict[str, tuple[Any, float]]" = OrderedDict()

    def _purge_expired(self) -> None:
        now = time.monotonic()
        expired = [k for k, (_, expires_at) in self._data.items() if expires_at <= now]
        for key in expired:
            self._data.pop(key, None)

    def __getitem__(self, key: str) -> Any:
        self._purge_expired()
        if key not in self._data:
            raise KeyError(key)
        value, expires_at = self._data.pop(key)
        if expires_at <= time.monotonic():
            raise KeyError(key)
        # Refresh LRU position and TTL on read.
        self._data[key] = (value, time.monotonic() + self.ttl_seconds)
        return value

    def __setitem__(self, key: str, value: Any) -> None:
        self._purge_expired()
        if key in self._data:
            self._data.pop(key, None)
        self._data[key] = (value, time.monotonic() + self.ttl_seconds)
        while len(self._data) > self.max_size:
            self._data.popitem(last=False)

    def __delitem__(self, key: str) -> None:
        self._purge_expired()
        if key not in self._data:
            raise KeyError(key)
        self._data.pop(key, None)

    def __iter__(self) -> Iterator[str]:
        self._purge_expired()
        return iter(self._data.keys())

    def __len__(self) -> int:
        self._purge_expired()
        return len(self._data)

    def __contains__(self, key: object) -> bool:
        if not isinstance(key, str):
            return False
        try:
            self.__getitem__(key)
            return True
        except KeyError:
            return False

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self.__getitem__(key)
        except KeyError:
            return default

    def pop(self, key: str, default: Any = _MISSING) -> Any:
        self._purge_expired()
        if key in self._data:
            value, _ = self._data.pop(key)
            return value
        if default is self._MISSING:
            raise KeyError(key)
        return default

    def clear(self) -> None:
        self._data.clear()

    def update(self, other: Dict[str, Any] | None = None, **kwargs: Any) -> None:
        source = other or {}
        for key, value in source.items():
            self.__setitem__(str(key), value)
        for key, value in kwargs.items():
            self.__setitem__(str(key), value)
