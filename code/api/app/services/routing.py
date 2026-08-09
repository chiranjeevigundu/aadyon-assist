"""Model routing: resolve a task tier to a concrete (provider, model, params).

Tiers map to (provider, model) via config.default_routes, configurable through the
environment. Kept deliberately simple — no per-user DB table to manage.
"""
from app.core.config import get_settings


def resolve(tier: str) -> dict:
    """Return {provider, model, temperature} for a tier (e.g. 'reasoning')."""
    routes = get_settings().default_routes
    provider, model = routes.get(tier, routes["reasoning"])
    return {"provider": provider, "model": model, "temperature": 0.2}
