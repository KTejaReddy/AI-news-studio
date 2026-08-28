"""ProviderManager for registering and querying active B-roll media generator providers.
"""

import logging
from typing import Dict, List, Optional

from core.broll.providers.base_provider import BrollProvider
from core.broll.providers.mock_providers import (
    GeminiFlowProvider,
    VeoProvider,
    RunwayProvider,
    PikaProvider,
    LumaProvider,
    KlingProvider,
    HailuoProvider,
    ComfyUIProvider,
    StableDiffusionProvider,
    FluxProvider,
    FuProvider,
)


class ProviderManager:
    """Manages registered B-roll visual generator models and selects active engine driver."""

    def __init__(self) -> None:
        """Initialize the ProviderManager."""
        self._logger = logging.getLogger(self.__class__.__name__)
        self.providers: Dict[str, BrollProvider] = {}
        self.active_provider_name: str = ""

        # Auto-register all supported providers
        self.register_provider(GeminiFlowProvider())
        self.register_provider(VeoProvider())
        self.register_provider(RunwayProvider())
        self.register_provider(PikaProvider())
        self.register_provider(LumaProvider())
        self.register_provider(KlingProvider())
        self.register_provider(HailuoProvider())
        self.register_provider(ComfyUIProvider())
        self.register_provider(StableDiffusionProvider())
        self.register_provider(FluxProvider())
        self.register_provider(FuProvider())

        # Set default active provider
        if self.providers:
            self.set_active_provider("Gemini Flow")

    def register_provider(self, provider: BrollProvider) -> None:
        """Register a B-roll generator provider driver.

        Args:
            provider: Concrete BrollProvider subclass instance.
        """
        name = provider.get_name()
        self.providers[name] = provider
        self._logger.info(f"Registered B-roll provider: {name}")

    def list_providers(self) -> List[str]:
        """List all registered B-roll provider names.

        Returns:
            List of strings.
        """
        return list(self.providers.keys())

    def get_active_provider(self) -> Optional[BrollProvider]:
        """Retrieve the currently selected B-roll generator provider driver.

        Returns:
            BrollProvider or None if not set.
        """
        return self.providers.get(self.active_provider_name)

    def set_active_provider(self, name: str) -> bool:
        """Set the active B-roll provider.

        Args:
            name: Provider name to set as active.

        Returns:
            True if set successfully, False otherwise.
        """
        if name in self.providers:
            self.active_provider_name = name
            self._logger.info(f"Selected active B-roll provider: {name}")
            return True
        else:
            self._logger.warning(f"Attempted to activate unregistered B-roll provider: {name}")
            return False
