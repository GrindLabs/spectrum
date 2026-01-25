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

```python
from spectrum import BrowserConfig, BrowserManager

manager = BrowserManager()
config = BrowserConfig(
    proxy="http://127.0.0.1:8080",
    window_size=(1280, 800),
    viewport=(1280, 720),
)
instance = manager.launch(config)
print(instance.endpoint)
manager.close_all()
```

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
