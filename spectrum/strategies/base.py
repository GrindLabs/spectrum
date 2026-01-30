import inspect
from dataclasses import dataclass
from typing import Awaitable, Optional, Protocol, Sequence

from ..config import BrowserConfig


@dataclass(frozen=True)
class NavigationContext:
    """Shared context for navigation-time strategies."""

    url: str
    instance_id: str
    config: BrowserConfig
    target_id: Optional[str] = None


class NavigationStrategy(Protocol):
    """Strategy hooks for navigation events."""

    name: str

    def before_navigation(self, context: NavigationContext) -> Optional[Awaitable[None]]:
        """Run before navigation begins."""

    def after_navigation(self, context: NavigationContext) -> Optional[Awaitable[None]]:
        """Run after navigation completes."""


def run_before_navigation(strategies: Sequence[NavigationStrategy], context: NavigationContext) -> None:
    """Run synchronous before-navigation hooks."""

    for strategy in strategies:
        result = strategy.before_navigation(context)
        if inspect.isawaitable(result):
            raise TypeError(f"Strategy {strategy.name} returned awaitable in sync context")


def run_after_navigation(strategies: Sequence[NavigationStrategy], context: NavigationContext) -> None:
    """Run synchronous after-navigation hooks."""

    for strategy in strategies:
        result = strategy.after_navigation(context)
        if inspect.isawaitable(result):
            raise TypeError(f"Strategy {strategy.name} returned awaitable in sync context")


async def run_before_navigation_async(
    strategies: Sequence[NavigationStrategy],
    context: NavigationContext,
) -> None:
    """Run async before-navigation hooks."""

    for strategy in strategies:
        result = strategy.before_navigation(context)
        if inspect.isawaitable(result):
            await result


async def run_after_navigation_async(
    strategies: Sequence[NavigationStrategy],
    context: NavigationContext,
) -> None:
    """Run async after-navigation hooks."""

    for strategy in strategies:
        result = strategy.after_navigation(context)
        if inspect.isawaitable(result):
            await result
