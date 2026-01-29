import asyncio
import json
import subprocess
import time
from typing import Optional
from uuid import uuid4

import aiohttp
import websockets

from .. import settings
from ..config import BrowserConfig
from ..ports import get_free_port
from ..runtime import build_flags, resolve_browser_path, resolve_profile_dir


class AsyncBrowserInstance:
    """Running browser instance launched via subprocess (asyncio)."""

    config: BrowserConfig
    id: str
    profile_dir: str
    browser_path: str
    port: int
    process: Optional[asyncio.subprocess.Process]
    current_target_id: Optional[str]
    current_url: Optional[str]

    def __init__(self, config: BrowserConfig) -> None:
        """Initialize the instance and resolve its runtime values."""

        self.config = config
        self.id = uuid4().hex[: settings.INSTANCE_ID_LENGTH]
        self.profile_dir = resolve_profile_dir(config, self.id)
        self.browser_path = resolve_browser_path(config)
        self.port = config.remote_debugging_port or get_free_port()
        self.process = None
        self.current_target_id = None
        self.current_url = None

    @property
    def endpoint(self) -> str:
        """Return the CDP endpoint URL."""

        return settings.ENDPOINT_TEMPLATE.format(
            host=settings.REMOTE_DEBUGGING_ADDRESS,
            port=self.port,
        )

    async def start(self) -> asyncio.subprocess.Process:
        """Start the browser process if it is not running."""

        if self.process and self.process.returncode is None:
            return self.process

        args = [self.browser_path, *build_flags(self.config, self.port, self.profile_dir)]
        self.process = await asyncio.create_subprocess_exec(
            *args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            close_fds=True,
        )

        return self.process

    async def goto(self, url: str) -> dict:
        """Open a new page via the CDP WebSocket endpoint."""

        if not url:
            raise ValueError("url is required")

        await self.start()
        await self._wait_for_cdp()

        ws_url = await self._browser_websocket_url()
        result = await self._send_cdp_command(
            ws_url,
            "Target.createTarget",
            {"url": url},
        )

        self.current_target_id = result.get("targetId")
        self.current_url = url

        return result

    async def content(self) -> str:
        """Return the page HTML for the current target."""

        if not self.current_target_id:
            raise RuntimeError("No current target; call goto() first")

        await self.start()
        await self._wait_for_cdp()

        ws_url = await self._target_websocket_url(self.current_target_id)
        await self._wait_for_dom_ready(ws_url, self.current_url)
        await self._wait_for_content_ready(ws_url, self.current_url)
        document = await self._send_cdp_command(
            ws_url,
            "DOM.getDocument",
            {"depth": 0, "pierce": True},
        )
        root = document.get("root", {})
        node_id = root.get("nodeId")

        if not node_id:
            raise RuntimeError("Missing document node id")

        result = await self._send_cdp_command(
            ws_url,
            "DOM.getOuterHTML",
            {"nodeId": node_id},
        )
        outer_html = result.get("outerHTML")

        if outer_html is None:
            raise RuntimeError("Missing page content result")

        return outer_html

    async def close(self) -> None:
        """Terminate the browser process."""

        if not self.process:
            return

        if self.process.returncode is None:
            self.process.terminate()

        try:
            await asyncio.wait_for(self.process.wait(), timeout=settings.SHUTDOWN_TIMEOUT_SECONDS)
        except asyncio.TimeoutError:
            self.process.kill()

    async def _wait_for_cdp(self) -> None:
        """Wait until the CDP HTTP endpoint is reachable."""

        deadline = time.monotonic() + settings.STARTUP_TIMEOUT_SECONDS
        target_url = f"{self.endpoint}/json/version"
        last_error: Optional[Exception] = None
        timeout = aiohttp.ClientTimeout(total=settings.STARTUP_POLL_INTERVAL_SECONDS)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            while time.monotonic() < deadline:
                try:
                    async with session.get(target_url) as response:
                        if response.status == 200:
                            return
                except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                    last_error = exc

                await asyncio.sleep(settings.STARTUP_POLL_INTERVAL_SECONDS)

        raise TimeoutError("CDP endpoint did not become available") from last_error

    async def _wait_for_dom_ready(self, ws_url: str, expected_url: Optional[str]) -> None:
        """Wait until the document readyState is complete."""

        deadline = time.monotonic() + settings.PAGE_LOAD_TIMEOUT_SECONDS

        while time.monotonic() < deadline:
            if await self._document_url_ready(ws_url, expected_url):
                return

            remaining = deadline - time.monotonic()

            if remaining <= 0:
                return

            try:
                await self._wait_for_page_load_event(ws_url, remaining)
            except TimeoutError:
                return

    async def _wait_for_content_ready(self, ws_url: str, expected_url: Optional[str]) -> None:
        """Wait for navigation to complete."""

        if not expected_url:
            return

        deadline = time.monotonic() + settings.PAGE_LOAD_TIMEOUT_SECONDS

        while time.monotonic() < deadline:
            document_url = await self._document_url(ws_url)

            if isinstance(document_url, str) and document_url.startswith(expected_url) and document_url != "about:blank":
                return

            await asyncio.sleep(settings.STARTUP_POLL_INTERVAL_SECONDS)

    async def _document_url(self, ws_url: str) -> Optional[str]:
        """Return the current document URL via the DOM domain."""

        result = await self._send_cdp_command(
            ws_url,
            "DOM.getDocument",
            {"depth": 0, "pierce": True},
        )
        root = result.get("root", {})

        return root.get("documentURL")

    async def _document_url_ready(self, ws_url: str, expected_url: Optional[str]) -> bool:
        """Check whether the document has a usable URL."""

        document_url = await self._document_url(ws_url)

        if not document_url:
            return False

        if document_url == "about:blank":
            return False

        if expected_url and not document_url.startswith(expected_url):
            return False

        return True

    async def _wait_for_page_load_event(self, ws_url: str, timeout: float) -> None:
        """Wait for Page.loadEventFired on the target."""

        if timeout <= 0:
            raise TimeoutError("Timed out waiting for Page.loadEventFired")

        message_id = 1
        payload = {"id": message_id, "method": "Page.enable", "params": {}}
        deadline = time.monotonic() + timeout

        async with websockets.connect(ws_url, open_timeout=settings.WEBSOCKET_TIMEOUT_SECONDS) as ws:
            await ws.send(json.dumps(payload))

            while True:
                remaining = deadline - time.monotonic()

                if remaining <= 0:
                    raise TimeoutError("Timed out waiting for Page.loadEventFired")

                raw = await asyncio.wait_for(ws.recv(), timeout=remaining)

                if not raw:
                    continue

                message = json.loads(raw)

                if message.get("id") == message_id:
                    if "error" in message:
                        raise RuntimeError(message["error"])
                    continue

                if message.get("method") == "Page.loadEventFired":
                    return

    async def _browser_websocket_url(self) -> str:
        """Return the browser-level WebSocket debugger URL."""

        target_url = f"{self.endpoint}/json/version"
        timeout = aiohttp.ClientTimeout(total=settings.WEBSOCKET_TIMEOUT_SECONDS)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(target_url) as response:
                payload = await response.text()

        data = json.loads(payload)
        ws_url = data.get("webSocketDebuggerUrl")

        if not ws_url:
            raise RuntimeError("Missing webSocketDebuggerUrl from CDP version endpoint")

        return ws_url

    async def _target_websocket_url(self, target_id: str) -> str:
        """Return the target WebSocket debugger URL."""

        target_url = f"{self.endpoint}/json/list"
        timeout = aiohttp.ClientTimeout(total=settings.WEBSOCKET_TIMEOUT_SECONDS)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(target_url) as response:
                payload = await response.text()

        data = json.loads(payload)

        for entry in data:
            entry_id = entry.get("id") or entry.get("targetId")

            if entry_id == target_id:
                ws_url = entry.get("webSocketDebuggerUrl")

                if not ws_url:
                    raise RuntimeError("Missing webSocketDebuggerUrl for target")

                return ws_url

        raise RuntimeError("Target not found")

    async def _send_cdp_command(self, ws_url: str, method: str, params: Optional[dict] = None) -> dict:
        """Send a single CDP command over WebSocket and return the result."""

        message_id = 1
        payload = {"id": message_id, "method": method, "params": params or {}}

        async with websockets.connect(ws_url, open_timeout=settings.WEBSOCKET_TIMEOUT_SECONDS) as ws:
            await ws.send(json.dumps(payload))

            while True:
                raw = await asyncio.wait_for(ws.recv(), timeout=settings.WEBSOCKET_TIMEOUT_SECONDS)

                if not raw:
                    continue

                message = json.loads(raw)

                if message.get("id") != message_id:
                    continue

                if "error" in message:
                    raise RuntimeError(message["error"])

                return message.get("result", {})
