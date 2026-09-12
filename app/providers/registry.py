from __future__ import annotations
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class ProviderAttempt:
    name: str
    error: str


class AllProvidersFailed(RuntimeError):
    def __init__(self, attempts: list[ProviderAttempt]):
        self.attempts = attempts
        super().__init__("; ".join(f"{x.name}: {x.error}" for x in attempts))


class ProviderRegistry(Generic[T]):
    """Ordered compatible providers; fallback never changes the requested capability."""

    def __init__(self, capability: str, providers: list[tuple[str, T]]):
        if not providers:
            raise ValueError("at least one provider is required")
        self.capability = capability
        self.providers = providers

    async def call(self, operation: Callable[[T], Awaitable[object]]) -> object:
        attempts = []
        for name, provider in self.providers:
            if getattr(provider, "capability", self.capability) != self.capability:
                continue
            try:
                return await operation(provider)
            except (TimeoutError, ConnectionError, OSError) as exc:
                attempts.append(ProviderAttempt(name, str(exc)))
        raise AllProvidersFailed(attempts)
