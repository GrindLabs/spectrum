from dataclasses import dataclass, field
from typing import TYPE_CHECKING, List, Optional, Tuple

from . import settings

if TYPE_CHECKING:
    from .strategies.base import NavigationStrategy


@dataclass(frozen=True)
class BrowserConfig:
    """Configuration for a browser instance."""

    browser_path: Optional[str] = None
    profile_dir: Optional[str] = None
    proxy: Optional[str] = None
    window_size: Optional[Tuple[int, int]] = settings.DEFAULT_WINDOW_SIZE
    viewport: Optional[Tuple[int, int]] = settings.DEFAULT_VIEWPORT
    remote_debugging_port: Optional[int] = None
    extra_flags: List[str] = field(default_factory=list)
    navigation_strategies: List["NavigationStrategy"] = field(default_factory=list)
