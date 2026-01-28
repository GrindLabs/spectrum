import json
import subprocess
import time
from typing import Optional
from urllib import request
from urllib.error import URLError
from uuid import uuid4

from websocket import create_connection

from .. import settings
from ..config import BrowserConfig
from ..ports import get_free_port
from ..runtime import build_flags, resolve_browser_path, resolve_profile_dir


class BrowserInstance:
    """Running browser instance launched via subprocess."""

    config: BrowserConfig
    id: str
    profile_dir: str
    browser_path: str
    port: int
    process: Optional[subprocess.Popen]
    current_target_id: Optional[str]
    current_url: Optional[str]

    def __init__(self, config: BrowserConfig) -> None:
        """Initialize the instance and resolve its runtime values."""

        self.config = config
        self.id = uuid4().hex[: settings.INSTANCE_ID_LENGTH]
        self.profile_dir = resolve_profile_dir(config, self.id)
        self.browser_path = resolve_browser_path(config)
        self.port = config.remote_debugging_port or get_free_port()
        self.process: Optional[subprocess.Popen] = None
        self.current_target_id: Optional[str] = None
        self.current_url: Optional[str] = None

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

        args = [self.browser_path, *build_flags(self.config, self.port, self.profile_dir)]
        self.process = subprocess.Popen(
            args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            close_fds=True,
        )

        return self.process

    def goto(self, url: str) -> dict:
        """Open a new page via the CDP WebSocket endpoint."""

        if not url:
            raise ValueError("url is required")

        self.start()
        self._wait_for_cdp()

        ws_url = self._browser_websocket_url()
        result = self._send_cdp_command(
            ws_url,
            "Target.createTarget",
            {"url": url},
        )

        self.current_target_id = result.get("targetId")
        self.current_url = url

        return result

    @property
    def content(self) -> str:
        """Return the page HTML for the current target."""

        if not self.current_target_id:
            raise RuntimeError("No current target; call goto() first")

        self.start()
        self._wait_for_cdp()

        ws_url = self._target_websocket_url(self.current_target_id)
        self._wait_for_dom_ready(ws_url, self.current_url)
        result = self._send_cdp_command(
            ws_url,
            "Runtime.evaluate",
            {"expression": "document.documentElement.outerHTML", "returnByValue": True},
        )

        if result.get("exceptionDetails"):
            raise RuntimeError("Failed to retrieve page content")

        value = result.get("result", {}).get("value")

        if value is None:
            raise RuntimeError("Missing page content result")

        return value

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

    def _wait_for_cdp(self) -> None:
        """Wait until the CDP HTTP endpoint is reachable."""

        deadline = time.monotonic() + settings.STARTUP_TIMEOUT_SECONDS
        target_url = f"{self.endpoint}/json/version"
        last_error: Optional[Exception] = None

        while time.monotonic() < deadline:
            try:
                with request.urlopen(target_url) as response:
                    if response.status == 200:
                        return
            except URLError as exc:
                last_error = exc

            time.sleep(settings.STARTUP_POLL_INTERVAL_SECONDS)

        raise TimeoutError("CDP endpoint did not become available") from last_error

    def _wait_for_dom_ready(self, ws_url: str, expected_url: Optional[str]) -> None:
        """Wait until the document readyState is complete."""

        deadline = time.monotonic() + settings.WEBSOCKET_TIMEOUT_SECONDS

        while time.monotonic() < deadline:
            result = self._send_cdp_command(
                ws_url,
                "Runtime.evaluate",
                {
                    "expression": "({readyState: document.readyState, href: document.location.href})",
                    "returnByValue": True,
                },
            )
            value = result.get("result", {}).get("value", {})
            state = value.get("readyState")
            href = value.get("href")

            if state == "complete" and (not expected_url or href != "about:blank"):
                return

            time.sleep(settings.STARTUP_POLL_INTERVAL_SECONDS)

    def _browser_websocket_url(self) -> str:
        """Return the browser-level WebSocket debugger URL."""

        target_url = f"{self.endpoint}/json/version"

        with request.urlopen(target_url) as response:
            payload = response.read().decode("utf-8")

        data = json.loads(payload)
        ws_url = data.get("webSocketDebuggerUrl")

        if not ws_url:
            raise RuntimeError("Missing webSocketDebuggerUrl from CDP version endpoint")

        return ws_url

    def _target_websocket_url(self, target_id: str) -> str:
        """Return the target WebSocket debugger URL."""

        target_url = f"{self.endpoint}/json/list"

        with request.urlopen(target_url) as response:
            payload = response.read().decode("utf-8")

        data = json.loads(payload)

        for entry in data:
            entry_id = entry.get("id") or entry.get("targetId")

            if entry_id == target_id:
                ws_url = entry.get("webSocketDebuggerUrl")

                if not ws_url:
                    raise RuntimeError("Missing webSocketDebuggerUrl for target")

                return ws_url

        raise RuntimeError("Target not found")

    def _send_cdp_command(self, ws_url: str, method: str, params: Optional[dict] = None) -> dict:
        """Send a single CDP command over WebSocket and return the result."""

        message_id = 1
        payload = {"id": message_id, "method": method, "params": params or {}}
        ws = create_connection(ws_url, timeout=settings.WEBSOCKET_TIMEOUT_SECONDS)

        try:
            ws.send(json.dumps(payload))

            while True:
                raw = ws.recv()

                if not raw:
                    continue

                message = json.loads(raw)

                if message.get("id") != message_id:
                    continue

                if "error" in message:
                    raise RuntimeError(message["error"])

                return message.get("result", {})
        finally:
            ws.close()
