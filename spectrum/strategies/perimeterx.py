import json
import random
import time
from typing import Optional
from urllib import request

from websocket import create_connection

from .. import settings
from .base import NavigationContext


class PerimeterXStrategy:
    """Non-evasive placeholder strategy for PerimeterX integrations."""

    name = "perimeterx"
    _button_timeout_seconds = 12.0
    _button_poll_interval_seconds = 0.4
    _hold_duration_seconds = 4.0
    _move_min_duration_seconds = 0.6
    _move_max_duration_seconds = 1.2

    def before_navigation(self, context: NavigationContext) -> None:
        return None

    def after_navigation(self, context: NavigationContext) -> None:
        if not context.target_id:
            return None

        port = context.config.remote_debugging_port
        if port is None:
            return None

        ws_url = self._target_websocket_url(port, context.target_id)
        self._press_and_hold_button(ws_url)
        return None

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

    def _press_and_hold_button(self, ws_url: str) -> None:
        ws = create_connection(ws_url, timeout=settings.WEBSOCKET_TIMEOUT_SECONDS)
        try:
            message_id = 1
            button_location, message_id = self._wait_for_button(ws, message_id)
            if not button_location:
                return

            message_id = self._move_mouse_humanlike(
                ws,
                message_id,
                x=button_location["x"],
                y=button_location["y"],
            )
            message_id = self._dispatch_mouse_event(
                ws,
                message_id,
                event_type="mousePressed",
                x=button_location["x"],
                y=button_location["y"],
                buttons=1,
            )
            time.sleep(self._hold_duration_seconds)
            self._dispatch_mouse_event(
                ws,
                message_id,
                event_type="mouseReleased",
                x=button_location["x"],
                y=button_location["y"],
                buttons=0,
            )
        finally:
            ws.close()

    def _wait_for_button(self, ws, message_id: int) -> tuple[Optional[dict], int]:
        deadline = time.monotonic() + self._button_timeout_seconds

        while time.monotonic() < deadline:
            payload, message_id = self._evaluate_for_button(ws, message_id)
            if payload:
                return payload, message_id
            time.sleep(self._button_poll_interval_seconds)

        return None, message_id

    def _evaluate_for_button(self, ws, message_id: int) -> tuple[Optional[dict], int]:
        expression = """
        (() => {
            const matcher = /press\\s*(?:&|and)?\\s*hold/i;
            const selectors = [
                "button",
                "[role='button']",
                "div",
                "span",
                "a",
            ];
            const candidates = document.querySelectorAll(selectors.join(","));
            for (const node of candidates) {
                const text = (node.innerText || node.textContent || "").trim();
                if (!text || !matcher.test(text)) {
                    continue;
                }
                const rect = node.getBoundingClientRect();
                if (!rect || rect.width === 0 || rect.height === 0) {
                    continue;
                }
                return {
                    x: rect.left + rect.width / 2,
                    y: rect.top + rect.height / 2,
                };
            }
            return null;
        })()
        """
        params = {"expression": expression, "returnByValue": True}
        result, message_id = self._send_cdp_command_on_ws(ws, message_id, "Runtime.evaluate", params)
        return result.get("result", {}).get("value"), message_id

    def _dispatch_mouse_event(
        self,
        ws,
        message_id: int,
        event_type: str,
        x: float,
        y: float,
        buttons: int,
    ) -> int:
        params = {
            "type": event_type,
            "x": x,
            "y": y,
            "button": "left",
            "buttons": buttons,
            "clickCount": 1,
        }
        _, message_id = self._send_cdp_command_on_ws(ws, message_id, "Input.dispatchMouseEvent", params)
        return message_id

    def _move_mouse_humanlike(self, ws, message_id: int, x: float, y: float) -> int:
        start_x = x + random.uniform(-120, -40)
        start_y = y + random.uniform(-80, -30)
        steps = random.randint(12, 22)
        duration = random.uniform(self._move_min_duration_seconds, self._move_max_duration_seconds)
        step_delay = duration / steps

        for step in range(steps):
            t = (step + 1) / steps
            ease = t * t * (3 - 2 * t)
            jitter_x = random.uniform(-1.5, 1.5)
            jitter_y = random.uniform(-1.0, 1.0)
            next_x = start_x + (x - start_x) * ease + jitter_x
            next_y = start_y + (y - start_y) * ease + jitter_y
            message_id = self._dispatch_mouse_event(
                ws,
                message_id,
                event_type="mouseMoved",
                x=next_x,
                y=next_y,
                buttons=0,
            )
            time.sleep(step_delay)

        return message_id

    def _send_cdp_command_on_ws(self, ws, message_id: int, method: str, params: dict) -> tuple[dict, int]:
        payload = {"id": message_id, "method": method, "params": params}
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
