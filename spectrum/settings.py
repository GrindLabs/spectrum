from typing import Final, Optional, Sequence, Tuple

PROFILE_BASE_DIR: Final[str] = "/tmp"
PROFILE_PREFIX: Final[str] = "spectrum-profile"
PATH_SEPARATOR: Final[str] = "/"
WINDOW_SIZE_SEPARATOR: Final[str] = ","
INSTANCE_ID_LENGTH: Final[int] = 8
ENDPOINT_TEMPLATE: Final[str] = "http://{host}:{port}"

REMOTE_DEBUGGING_ADDRESS: Final[str] = "127.0.0.1"
REMOTE_DEBUGGING_PORT_FALLBACK: Final[int] = 0

FREE_PORT_HOST: Final[str] = REMOTE_DEBUGGING_ADDRESS
FREE_PORT_EPHEMERAL_PORT: Final[int] = 0

DEFAULT_WINDOW_SIZE: Final[Tuple[int, int]] = (1280, 800)
DEFAULT_VIEWPORT: Final[Optional[Tuple[int, int]]] = None

REMOTE_DEBUGGING_PORT_FLAG: Final[str] = "--remote-debugging-port"
REMOTE_DEBUGGING_ADDRESS_FLAG: Final[str] = "--remote-debugging-address"
USER_DATA_DIR_FLAG: Final[str] = "--user-data-dir"
WINDOW_SIZE_FLAG: Final[str] = "--window-size"
PROXY_SERVER_FLAG: Final[str] = "--proxy-server"

DEFAULT_FLAGS: Final[Sequence[str]] = (
    "--no-first-run",
    "--no-startup-window",
    "--no-default-browser-check",
    "--disable-popup-blocking",
    "--disable-notifications",
    "--disable-background-networking",
    "--disable-background-timer-throttling",
    "--disable-client-side-phishing-detection",
    "--disable-renderer-backgrounding",
    "--disable-dev-shm-usage",
    "--metrics-recording-only",
    "--no-service-autorun",
    "--password-store=basic",
    "--use-mock-keychain",
    "--disable-blink-features=AutomationControlled",
    "--disable-infobars",
    "--remote-allow-origins=*",
    "--disable-sync",
    "--disable-translate",
    "--disable-logging",
    "--disable-gpu",
    "--disable-software-rasterizer",
    "--disable-hang-monitor",
    "--disable-telemetry",
    "--disable-crash-reporter",
    "--disable-save-password-bubble",
    "--disable-prompt-on-repost",
    "--start-maximized",
    "--disable-backgrounding-occluded-windows",
    "--homepage=about:blank",
    "--disable-ipc-flooding-protection",
    "--disable-session-crashed-bubble",
    "--force-fieldtrials=*BackgroundTracing/default/",
    "--disable-breakpad",
    "--disable-features=IsolateOrigins,site-per-process",
    "--no-pings",
    "--disable-component-update",
    "--disable-default-apps",
    "--disable-domain-reliability",
)

LINUX_EXTRA_FLAGS: Final[Sequence[str]] = ("--no-sandbox",)

PLATFORM_DARWIN: Final[str] = "darwin"
PLATFORM_LINUX_PREFIX: Final[str] = "linux"

CHROME_PATHS_DARWIN: Final[Sequence[str]] = (
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
)

CHROME_PATHS_LINUX: Final[Sequence[str]] = (
    "/usr/bin/google-chrome",
    "/usr/bin/google-chrome-stable",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
)

SHUTDOWN_TIMEOUT_SECONDS: Final[int] = 5
ERROR_CHROME_NOT_FOUND: Final[str] = "Chrome executable not found"
