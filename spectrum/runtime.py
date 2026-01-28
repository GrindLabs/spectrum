import sys
from pathlib import Path
from typing import List, Optional, Tuple

from . import settings
from .config import BrowserConfig


def resolve_profile_dir(config: BrowserConfig, instance_id: str) -> str:
    """Return a profile directory under the base dir."""

    base_dir = Path(settings.PROFILE_BASE_DIR)

    if config.profile_dir:
        candidate = Path(config.profile_dir)
        candidate_value = str(candidate)

        if not candidate_value.startswith(settings.PROFILE_BASE_DIR + settings.PATH_SEPARATOR) and candidate_value != settings.PROFILE_BASE_DIR:
            candidate = base_dir / candidate.name

        candidate.mkdir(parents=True, exist_ok=True)

        return str(candidate)

    profile_dir = base_dir / f"{settings.PROFILE_PREFIX}-{instance_id}"
    profile_dir.mkdir(parents=True, exist_ok=True)

    return str(profile_dir)


def resolve_browser_path(config: BrowserConfig) -> str:
    """Resolve the browser executable path."""

    if config.browser_path:
        return config.browser_path

    candidates = default_browser_paths()

    for path in candidates:
        if Path(path).exists():
            return path

    raise FileNotFoundError(settings.ERROR_CHROME_NOT_FOUND)


def default_browser_paths() -> List[str]:
    """Return default executable paths for the platform."""

    if sys.platform == settings.PLATFORM_DARWIN:
        return list(settings.CHROME_PATHS_DARWIN)

    if sys.platform.startswith(settings.PLATFORM_LINUX_PREFIX):
        return list(settings.CHROME_PATHS_LINUX)

    return []


def window_size(config: BrowserConfig) -> Optional[Tuple[int, int]]:
    """Return the window size to use for the browser."""

    if config.window_size:
        return config.window_size

    if config.viewport:
        return config.viewport

    return None


def build_flags(config: BrowserConfig, port: int, profile_dir: str) -> List[str]:
    """Build command-line flags for the browser process."""

    flags = [
        f"{settings.REMOTE_DEBUGGING_PORT_FLAG}={port}",
        f"{settings.REMOTE_DEBUGGING_ADDRESS_FLAG}={settings.REMOTE_DEBUGGING_ADDRESS}",
        f"{settings.USER_DATA_DIR_FLAG}={profile_dir}",
        *settings.DEFAULT_FLAGS,
    ]

    if sys.platform.startswith(settings.PLATFORM_LINUX_PREFIX):
        flags.extend(settings.LINUX_EXTRA_FLAGS)

    resolved_window_size = window_size(config)

    if resolved_window_size:
        flags.append(f"{settings.WINDOW_SIZE_FLAG}={resolved_window_size[0]}{settings.WINDOW_SIZE_SEPARATOR}{resolved_window_size[1]}")

    if config.proxy:
        flags.append(f"{settings.PROXY_SERVER_FLAG}={config.proxy}")

    if config.extra_flags:
        flags.extend(config.extra_flags)

    return flags
