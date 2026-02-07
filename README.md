# Spectrum

Small Python library that launches Chrome-based browsers with CDP enabled and
isolated profiles per instance.

## Prereqs

- Python 3.9+
- Chrome, Chromium, or any Chrome-based browser installed
- Optional: uv (https://github.com/astral-sh/uv)

## Install

```sh
python -m pip install -e .
```

## Usage

### Sync

```python
from spectrum.config import BrowserConfig
from spectrum.sync_spectrum import BrowserManager
from spectrum.strategies import ReconStrategy
manager = BrowserManager()
config = BrowserConfig(
    proxy="http://127.0.0.1:8080",
    window_size=(1280, 800),
    viewport=(1280, 720),
    remote_debugging_port=9222,
    strategy_overrides={
        "perimeterx": None,
        "recon": ReconStrategy(),
    },
)
instance = manager.launch(config)
print(instance.endpoint)
instance.goto("https://example.com")
# Example actions: scroll and click using CDP commands.
instance.actions(
    [
        {"method": "Input.dispatchMouseEvent", "params": {"type": "mouseWheel", "x": 640, "y": 360, "deltaY": 800}},
        {"method": "Input.dispatchMouseEvent", "params": {"type": "mouseMoved", "x": 250, "y": 520, "buttons": 0}},
        {
            "method": "Input.dispatchMouseEvent",
            "params": {"type": "mousePressed", "x": 250, "y": 520, "button": "left", "buttons": 1, "clickCount": 1},
        },
        {
            "method": "Input.dispatchMouseEvent",
            "params": {"type": "mouseReleased", "x": 250, "y": 520, "button": "left", "buttons": 0, "clickCount": 1},
        },
    ]
)
# Subsequent goto calls reuse the same tab.
page_html = instance.content
print(page_html)
manager.close_all()
```

### Async (asyncio)

```python
import asyncio

from spectrum.async_spectrum import AsyncBrowserManager
from spectrum.config import BrowserConfig
from spectrum.strategies import ReconStrategy

async def main() -> None:
    manager = AsyncBrowserManager()
    config = BrowserConfig(
        proxy="http://127.0.0.1:8080",
        window_size=(1280, 800),
        viewport=(1280, 720),
        remote_debugging_port=9222,
        strategy_overrides={
            "perimeterx": None,
            "recon": ReconStrategy(),
        },
    )
    instance = await manager.launch(config)
    print(instance.endpoint)
    await instance.goto("https://example.com")
    # Example actions: scroll and click using CDP commands.
    await instance.actions(
        [
            {"method": "Input.dispatchMouseEvent", "params": {"type": "mouseWheel", "x": 640, "y": 360, "deltaY": 800}},
            {"method": "Input.dispatchMouseEvent", "params": {"type": "mouseMoved", "x": 250, "y": 520, "buttons": 0}},
            {
                "method": "Input.dispatchMouseEvent",
                "params": {"type": "mousePressed", "x": 250, "y": 520, "button": "left", "buttons": 1, "clickCount": 1},
            },
            {
                "method": "Input.dispatchMouseEvent",
                "params": {"type": "mouseReleased", "x": 250, "y": 520, "button": "left", "buttons": 0, "clickCount": 1},
            },
        ]
    )
    # Subsequent goto calls reuse the same tab.
    page_html = await instance.content()
    print(page_html)
    await manager.close_all()


asyncio.run(main())
```

## API Reference

### Managers

- `BrowserManager.launch(config: BrowserConfig) -> BrowserInstance`
  - Starts a new browser process and returns a running instance.
- `BrowserManager.close_all() -> None`
  - Terminates all running instances started by the manager.
- `AsyncBrowserManager.launch(config: BrowserConfig) -> AsyncBrowserInstance`
  - Async version of `launch`.
- `AsyncBrowserManager.close_all() -> None`
  - Async version of `close_all`.

### BrowserInstance (sync)

- `endpoint: str`
  - CDP endpoint URL for the instance.
- `start() -> subprocess.Popen`
  - Starts the browser process if needed.
- `goto(url: str) -> dict`
  - Navigates to a URL and returns the CDP response.
- `actions(actions: list[dict]) -> dict`
  - Executes a list of CDP commands on the current tab and returns the last command result.
  - Each action must be `{"method": str, "params": dict}`.
  - Requires `goto()` to have been called at least once.
- `content: str`
  - HTML of the current page. Requires `goto()` first.
- `close() -> None`
  - Terminates the browser process.

### AsyncBrowserInstance (asyncio)

- `endpoint: str`
  - CDP endpoint URL for the instance.
- `start() -> asyncio.subprocess.Process`
  - Starts the browser process if needed.
- `goto(url: str) -> dict`
  - Navigates to a URL and returns the CDP response.
- `actions(actions: list[dict]) -> dict`
  - Async version of `actions`.
- `content() -> str`
  - HTML of the current page. Requires `goto()` first.
- `close() -> None`
  - Terminates the browser process.

## Examples

### Sync: navigate, actions, and content

```python
from spectrum.config import BrowserConfig
from spectrum.sync_spectrum import BrowserManager

manager = BrowserManager()
instance = manager.launch(BrowserConfig())
instance.goto("https://example.com")

instance.actions(
    [
        {"method": "Runtime.evaluate", "params": {"expression": "window.scrollTo(0, 600)"}},
        {"method": "Input.dispatchMouseEvent", "params": {"type": "mouseWheel", "x": 400, "y": 300, "deltaY": 600}},
    ]
)

page_html = instance.content
print(page_html)
manager.close_all()
```

### Async: navigate, actions, and content

```python
import asyncio

from spectrum.async_spectrum import AsyncBrowserManager
from spectrum.config import BrowserConfig

async def main() -> None:
    manager = AsyncBrowserManager()
    instance = await manager.launch(BrowserConfig())
    await instance.goto("https://example.com")
    await instance.actions(
        [
            {"method": "Runtime.evaluate", "params": {"expression": "window.scrollTo(0, 600)"}},
            {"method": "Input.dispatchMouseEvent", "params": {"type": "mouseWheel", "x": 400, "y": 300, "deltaY": 600}},
        ]
    )
    page_html = await instance.content()
    print(page_html)
    await manager.close_all()

asyncio.run(main())
```

### Recon behavior notes

- Navigation strategies are loaded by default (Recon + PerimeterX). Use
  `strategy_overrides` to replace or disable by name (set value to `None`).
- Recon runs before navigation to preflight tech/WAF signals.
- CAPTCHA providers are detected after navigation (HTML markers). If a CAPTCHA is
  detected and no strategy is available, `CaptchaFoundError` is raised and the
  browser is closed via CDP.
- If a WAF challenge is detected after navigation and no strategy exists, a
  `BanError` is raised and the browser is closed via CDP.
- WAF strategies (e.g., PerimeterX) are applied automatically when detected.

## Development

Install dev tooling and enable pre-commit:

```sh
uv pip install -e ".[dev]"
uv run pre-commit install
```

Alternatively with pip:

```sh
python -m pip install -e ".[dev]"
pre-commit install
```

Run the hooks manually:

```sh
uv run pre-commit run --all-files
```

Alternatively with pip:

```sh
pre-commit run --all-files
```
