import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Tuple
from uuid import uuid4

from . import settings
from .config import BrowserConfig
from .ports import get_free_port


class BrowserInstance:
    """Running browser instance launched via subprocess."""

    config: BrowserConfig
    id: str
    profile_dir: str
    browser_path: str
    port: int
    process: Optional[subprocess.Popen]

    def __init__(self, config: BrowserConfig) -> None:
        """Initialize the instance and resolve its runtime values."""

        self.config = config
        self.id = uuid4().hex[: settings.INSTANCE_ID_LENGTH]
        self.profile_dir = self._resolve_profile_dir()
        self.browser_path = self._resolve_browser_path()
        self.port = config.remote_debugging_port or get_free_port()
        self.process: Optional[subprocess.Popen] = None

    @property
    def endpoint(self) -> str:
        """Return the CDP endpoint URL."""

        return settings.ENDPOINT_TEMPLATE.format(
            host=settings.REMOTE_DEBUGGING_ADDRESS,
            port=self.port,
        )

    def start(self) -> subprocess.Popen:
        """Start the browser process if it is not running."""

        if self.process and self.process.poll() is None:

            return self.process

        args = [self.browser_path, *self._build_flags()]
        self.process = subprocess.Popen(
            args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            close_fds=True,
        )

        return self.process

    def close(self) -> None:
        """Terminate the browser process."""

        if not self.process:

            return

        if self.process.poll() is None:

            self.process.terminate()

        try:
            self.process.wait(timeout=settings.SHUTDOWN_TIMEOUT_SECONDS)

        except subprocess.TimeoutExpired:
            self.process.kill()

    def _resolve_profile_dir(self) -> str:
        """Return a profile directory under the base dir."""

        base_dir = Path(settings.PROFILE_BASE_DIR)

        if self.config.profile_dir:
            candidate = Path(self.config.profile_dir)
            candidate_value = str(candidate)

            if (
                not candidate_value.startswith(
                    settings.PROFILE_BASE_DIR + settings.PATH_SEPARATOR
                )
                and candidate_value != settings.PROFILE_BASE_DIR
            ):

                candidate = base_dir / candidate.name

            candidate.mkdir(parents=True, exist_ok=True)

            return str(candidate)

        profile_dir = base_dir / f"{settings.PROFILE_PREFIX}-{self.id}"
        profile_dir.mkdir(parents=True, exist_ok=True)

        return str(profile_dir)

    def _resolve_browser_path(self) -> str:
        """Resolve the browser executable path."""

        if self.config.browser_path:

            return self.config.browser_path

        candidates = self._default_browser_paths()

        for path in candidates:

            if Path(path).exists():

                return path

        raise FileNotFoundError(settings.ERROR_CHROME_NOT_FOUND)

    def _default_browser_paths(self) -> List[str]:
        """Return default executable paths for the platform."""

        if sys.platform == settings.PLATFORM_DARWIN:

            return list(settings.CHROME_PATHS_DARWIN)

        if sys.platform.startswith(settings.PLATFORM_LINUX_PREFIX):

            return list(settings.CHROME_PATHS_LINUX)

        return []

    def _window_size(self) -> Optional[Tuple[int, int]]:
        """Return the window size to use for the browser."""

        if self.config.window_size:

            return self.config.window_size

        if self.config.viewport:

            return self.config.viewport

        return None

    def _build_flags(self) -> List[str]:
        """Build command-line flags for the browser process."""

        flags = [
            f"{settings.REMOTE_DEBUGGING_PORT_FLAG}={self.port}",
            f"{settings.REMOTE_DEBUGGING_ADDRESS_FLAG}={settings.REMOTE_DEBUGGING_ADDRESS}",
            f"{settings.USER_DATA_DIR_FLAG}={self.profile_dir}",
            *settings.DEFAULT_FLAGS,
        ]

        if sys.platform.startswith(settings.PLATFORM_LINUX_PREFIX):

            flags.extend(settings.LINUX_EXTRA_FLAGS)

        window_size = self._window_size()

        if window_size:

            flags.append(
                f"{settings.WINDOW_SIZE_FLAG}={window_size[0]}"
                f"{settings.WINDOW_SIZE_SEPARATOR}{window_size[1]}"
            )

        if self.config.proxy:

            flags.append(f"{settings.PROXY_SERVER_FLAG}={self.config.proxy}")

        if self.config.extra_flags:

            flags.extend(self.config.extra_flags)

        return flags
