from typing import Dict, Optional

from .config import BrowserConfig
from .instance import BrowserInstance


class BrowserManager:
    """Manager for multiple browser instances."""

    instances: Dict[str, BrowserInstance]

    def __init__(self) -> None:
        """Initialize the manager."""

        self.instances: Dict[str, BrowserInstance] = {}

    def launch(self, config: BrowserConfig) -> BrowserInstance:
        """Launch and register a browser instance."""

        instance = BrowserInstance(config)
        instance.start()
        self.instances[instance.id] = instance

        return instance

    def get(self, instance_id: str) -> Optional[BrowserInstance]:
        """Return a known instance by id."""

        return self.instances.get(instance_id)

    def close(self, instance_id: str) -> None:
        """Close and remove an instance by id."""

        instance = self.instances.get(instance_id)

        if not instance:
            return

        instance.close()
        self.instances.pop(instance_id, None)

    def close_all(self) -> None:
        """Close all instances."""

        for instance in list(self.instances.values()):
            instance.close()

        self.instances.clear()
