from typing import Any, Callable, Dict, TypeVar
import torch.nn as nn


T = TypeVar('T', bound=nn.Module)


class ModelRegistry:
    """Registry for model classes with self-registration and dynamic discovery."""

    _registry: Dict[str, Callable[..., nn.Module]] = {}

    @classmethod
    def register(cls, name: str) -> Callable[[Callable[..., T]], Callable[..., T]]:
        """Decorator to register a model function/class with the given name."""

        def wrapper(model_fn: Callable[..., T]) -> Callable[..., T]:
            cls._registry[name] = model_fn
            return model_fn

        return wrapper

    @classmethod
    def get(cls, name: str, **kwargs: Any) -> nn.Module:
        """Get a model instance by name."""
        if name not in cls._registry:
            available = ", ".join(cls.list_models())
            raise ValueError(f"Model '{name}' not found. Available: {available}")
        return cls._registry[name](**kwargs)

    @classmethod
    def list_models(cls) -> list[str]:
        """Return list of registered model names."""
        return list(cls._registry.keys())

    @classmethod
    def is_registered(cls, name: str) -> bool:
        """Check if a model is registered."""
        return name in cls._registry

    @classmethod
    def clear(cls) -> None:
        """Clear all registered models (useful for testing)."""
        cls._registry.clear()


# Global registry instance
registry = ModelRegistry()


__all__ = ["ModelRegistry", "registry"]
