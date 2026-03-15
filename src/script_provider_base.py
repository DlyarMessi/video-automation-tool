from __future__ import annotations

from abc import ABC, abstractmethod

from src.intake_models import ScriptProviderRequest, ScriptProviderResponse


class ScriptProvider(ABC):
    provider_name: str = "base"

    @abstractmethod
    def generate(self, request: ScriptProviderRequest) -> ScriptProviderResponse:
        raise NotImplementedError
