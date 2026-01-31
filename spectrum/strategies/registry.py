from __future__ import annotations

from typing import Dict, Iterable, List, Optional

from .base import NavigationStrategy
from .perimeterx import PerimeterXStrategy
from .recon import ReconStrategy


def default_strategies() -> List[NavigationStrategy]:
    """Return default strategy instances (ordered)."""

    return [
        ReconStrategy(),
        PerimeterXStrategy(),
    ]


def merge_strategies(
    defaults: Iterable[NavigationStrategy],
    overrides: Dict[str, Optional[NavigationStrategy]],
    additions: Iterable[NavigationStrategy],
) -> List[NavigationStrategy]:
    """Merge default strategies with overrides and additions."""

    ordered: List[NavigationStrategy] = []
    index: Dict[str, int] = {}

    for strategy in defaults:
        name = getattr(strategy, "name", None)
        if not name:
            continue
        if name in index:
            ordered[index[name]] = strategy
        else:
            index[name] = len(ordered)
            ordered.append(strategy)

    for name, strategy in overrides.items():
        if strategy is None:
            if name in index:
                ordered.pop(index[name])
                index = {item.name: idx for idx, item in enumerate(ordered)}
            continue

        if name in index:
            ordered[index[name]] = strategy
        else:
            index[name] = len(ordered)
            ordered.append(strategy)

    for strategy in additions:
        name = getattr(strategy, "name", None)
        if not name:
            continue
        if name in index:
            ordered[index[name]] = strategy
        else:
            index[name] = len(ordered)
            ordered.append(strategy)

    return ordered
