import asyncio
import json
import logging
from typing import Dict, Optional
from urllib import request

import websockets
from websocket import create_connection

from .. import settings
from ..errors import BanError, CaptchaFoundError
from ..recon import ReconReport, detect_captcha, detect_waf, preflight_recon, preflight_recon_async
from .base import NavigationContext
from .perimeterx import PerimeterXStrategy

logger = logging.getLogger(__name__)


class ReconStrategy:
    """Recon strategy that detects WAFs/tech and applies WAF strategies."""

    name = "recon"

    def __init__(
        self,
        waf_strategy_factories: Optional[Dict[str, type]] = None,
        captcha_strategy_factories: Optional[Dict[str, type]] = None,
    ) -> None:
        self._reports: Dict[str, ReconReport] = {}
        self._waf_strategy_factories = waf_strategy_factories or {
            "perimeterx": PerimeterXStrategy,
        }
        self._captcha_strategy_factories = captcha_strategy_factories or {}

    def before_navigation(self, context: NavigationContext):
        if _is_async_context():
            return self._before_navigation_async(context)

        self._reports[context.instance_id] = preflight_recon(context.url)
        return None

    def after_navigation(self, context: NavigationContext):
        if _is_async_context():
            return self._after_navigation_async(context)

        if not context.target_id:
            return None

        report = self._reports.get(context.instance_id) or preflight_recon(context.url)
        html_sample = self._fetch_html_sync(context)
        if html_sample is None:
            return None

        self._handle_captcha(context, report, html_sample)
        self._handle_waf(context, report, html_sample)
        return None

    async def _before_navigation_async(self, context: NavigationContext) -> None:
        report = await preflight_recon_async(context.url)
        self._reports[context.instance_id] = report

    async def _after_navigation_async(self, context: NavigationContext) -> None:
        if not context.target_id:
            return

        report = self._reports.get(context.instance_id)
        if not report:
            report = await preflight_recon_async(context.url)

        html_sample = await self._fetch_html_async(context)
        if html_sample is None:
            return

        await self._handle_captcha_async(context, report, html_sample)
        await self._handle_waf_async(context, report, html_sample)

    def _handle_waf(self, context: NavigationContext, report: ReconReport, html_sample: str) -> None:
        html_waf_hits = detect_waf({}, html_sample)
        if not html_waf_hits:
            return

        waf_hits = set(report.waf_hits) | set(html_waf_hits)
        if not waf_hits:
            return

        for waf_name in html_waf_hits:
            if self._strategy_already_registered(context, waf_name):
                logger.debug("WAF %s strategy already configured", waf_name)
                continue

            strategy_factory = self._waf_strategy_factories.get(waf_name)
            if strategy_factory:
                logger.info("Applying WAF strategy for %s", waf_name)
                strategy_factory().after_navigation(context)
                return

            self._close_browser_sync(context)
            raise BanError(f"WAF challenge detected ({waf_name}); no strategy available")

    def _handle_captcha(self, context: NavigationContext, report: ReconReport, html_sample: str) -> None:
        html_captcha_hits = detect_captcha({}, html_sample)
        if not html_captcha_hits:
            return

        captcha_hits = set(report.captcha_hits) | set(html_captcha_hits)
        if not captcha_hits:
            return

        for captcha_name in html_captcha_hits:
            if self._strategy_already_registered(context, captcha_name):
                logger.debug("CAPTCHA %s strategy already configured", captcha_name)
                continue

            strategy_factory = self._captcha_strategy_factories.get(captcha_name)
            if strategy_factory:
                logger.info("Applying CAPTCHA strategy for %s", captcha_name)
                strategy_factory().after_navigation(context)
                return

            self._close_browser_sync(context)
            raise CaptchaFoundError(f"CAPTCHA detected ({captcha_name}); no strategy available yet")

    async def _handle_waf_async(
        self,
        context: NavigationContext,
        report: ReconReport,
        html_sample: str,
    ) -> None:
        html_waf_hits = detect_waf({}, html_sample)
        if not html_waf_hits:
            return

        waf_hits = set(report.waf_hits) | set(html_waf_hits)
        if not waf_hits:
            return

        for waf_name in html_waf_hits:
            if self._strategy_already_registered(context, waf_name):
                logger.debug("WAF %s strategy already configured", waf_name)
                continue

            strategy_factory = self._waf_strategy_factories.get(waf_name)
            if strategy_factory:
                logger.info("Applying WAF strategy for %s", waf_name)
                result = strategy_factory().after_navigation(context)
                if asyncio.iscoroutine(result):
                    await result
                return

            await self._close_browser_async(context)
            raise BanError(f"WAF challenge detected ({waf_name}); no strategy available")

    async def _handle_captcha_async(
        self,
        context: NavigationContext,
        report: ReconReport,
        html_sample: str,
    ) -> None:
        html_captcha_hits = detect_captcha({}, html_sample)
        if not html_captcha_hits:
            return

        captcha_hits = set(report.captcha_hits) | set(html_captcha_hits)
        if not captcha_hits:
            return

        for captcha_name in html_captcha_hits:
            if self._strategy_already_registered(context, captcha_name):
                logger.debug("CAPTCHA %s strategy already configured", captcha_name)
                continue

            strategy_factory = self._captcha_strategy_factories.get(captcha_name)
            if strategy_factory:
                logger.info("Applying CAPTCHA strategy for %s", captcha_name)
                result = strategy_factory().after_navigation(context)
                if asyncio.iscoroutine(result):
                    await result
                return

            await self._close_browser_async(context)
            raise CaptchaFoundError(f"CAPTCHA detected ({captcha_name}); no strategy available yet")

    def _strategy_already_registered(self, context: NavigationContext, waf_name: str) -> bool:
        for strategy in context.config.navigation_strategies:
            if getattr(strategy, "name", None) == waf_name and strategy is not self:
                return True
        return False

    def _fetch_html_sync(self, context: NavigationContext) -> Optional[str]:
        port = context.config.remote_debugging_port
        if port is None or not context.target_id:
            return None

        ws_url = self._target_websocket_url(port, context.target_id)
        ws = create_connection(ws_url, timeout=settings.WEBSOCKET_TIMEOUT_SECONDS)
        try:
            message_id = 1
            document, message_id = self._send_cdp_command_on_ws(
                ws,
                message_id,
                "DOM.getDocument",
                {"depth": 0, "pierce": True},
            )
            root = document.get("root", {})
            node_id = root.get("nodeId")
            if not node_id:
                return None

            result, _ = self._send_cdp_command_on_ws(
                ws,
                message_id,
                "DOM.getOuterHTML",
                {"nodeId": node_id},
            )
            return result.get("outerHTML")
        finally:
            ws.close()

    async def _fetch_html_async(self, context: NavigationContext) -> Optional[str]:
        port = context.config.remote_debugging_port
        if port is None or not context.target_id:
            return None

        ws_url = self._target_websocket_url(port, context.target_id)
        async with websockets.connect(
            ws_url,
            open_timeout=settings.WEBSOCKET_TIMEOUT_SECONDS,
            max_size=None,
        ) as ws:
            message_id = 1
            document, message_id = await self._send_cdp_command_on_ws_async(
                ws,
                message_id,
                "DOM.getDocument",
                {"depth": 0, "pierce": True},
            )
            root = document.get("root", {})
            node_id = root.get("nodeId")
            if not node_id:
                return None

            result, _ = await self._send_cdp_command_on_ws_async(
                ws,
                message_id,
                "DOM.getOuterHTML",
                {"nodeId": node_id},
            )
            return result.get("outerHTML")

    def _target_websocket_url(self, port: int, target_id: str) -> str:
        endpoint = settings.ENDPOINT_TEMPLATE.format(
            host=settings.REMOTE_DEBUGGING_ADDRESS,
            port=port,
        )
        target_url = f"{endpoint}/json/list"
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

    def _browser_websocket_url(self, port: int) -> str:
        endpoint = settings.ENDPOINT_TEMPLATE.format(
            host=settings.REMOTE_DEBUGGING_ADDRESS,
            port=port,
        )
        version_url = f"{endpoint}/json/version"
        with request.urlopen(version_url) as response:
            payload = response.read().decode("utf-8")
        data = json.loads(payload)
        ws_url = data.get("webSocketDebuggerUrl")
        if not ws_url:
            raise RuntimeError("Missing webSocketDebuggerUrl for browser")
        return ws_url

    def _close_browser_sync(self, context: NavigationContext) -> None:
        port = context.config.remote_debugging_port
        if port is None:
            return
        try:
            ws_url = self._browser_websocket_url(port)
            ws = create_connection(ws_url, timeout=settings.WEBSOCKET_TIMEOUT_SECONDS)
            try:
                self._send_cdp_command_on_ws(ws, 1, "Browser.close")
            finally:
                ws.close()
        except Exception as exc:
            logger.debug("Failed to close browser via CDP: %s", exc)

    async def _close_browser_async(self, context: NavigationContext) -> None:
        port = context.config.remote_debugging_port
        if port is None:
            return
        try:
            ws_url = self._browser_websocket_url(port)
            async with websockets.connect(
                ws_url,
                open_timeout=settings.WEBSOCKET_TIMEOUT_SECONDS,
                max_size=None,
            ) as ws:
                await self._send_cdp_command_on_ws_async(ws, 1, "Browser.close")
        except Exception as exc:
            logger.debug("Failed to close browser via CDP: %s", exc)

    def _send_cdp_command_on_ws(self, ws, message_id: int, method: str, params: Optional[dict] = None):
        payload = {"id": message_id, "method": method, "params": params or {}}
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
            return message.get("result", {}), message_id + 1

    async def _send_cdp_command_on_ws_async(
        self,
        ws: websockets.WebSocketClientProtocol,
        message_id: int,
        method: str,
        params: Optional[dict] = None,
    ):
        payload = {"id": message_id, "method": method, "params": params or {}}
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
            return message.get("result", {}), message_id + 1


def _is_async_context() -> bool:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return False
    return True
