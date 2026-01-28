from typing import Dict, Optional

from ..config import BrowserConfig
from .instance import AsyncBrowserInstance


class AsyncBrowserManager:
    """Manager for multiple browser instances."""

    instances: Dict[str, AsyncBrowserInstance]

    def __init__(self) -> None:
        """Initialize the manager."""

        self.instances: Dict[str, AsyncBrowserInstance] = {}

    async def launch(self, config: BrowserConfig) -> AsyncBrowserInstance:
        """Launch and register a browser instance."""

        instance = AsyncBrowserInstance(config)
        await instance.start()
        self.instances[instance.id] = instance

        return instance

    def get(self, instance_id: str) -> Optional[AsyncBrowserInstance]:
        """Return a known instance by id."""

        return self.instances.get(instance_id)

    async def close(self, instance_id: str) -> None:
        """Close and remove an instance by id."""

        instance = self.instances.get(instance_id)

        if not instance:
            return

        await instance.close()
        self.instances.pop(instance_id, None)

    async def close_all(self) -> None:
        """Close all instances."""

        for instance in list(self.instances.values()):
            await instance.close()

        self.instances.clear()
