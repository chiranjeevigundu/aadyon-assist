"""Model routing — a thin adapter over `llmkit.routing`.

Tiers map to (provider, model); agent code names a tier, never a vendor. The table
lives in `core.config.default_routes` and is passed through, so this deployment's
routes stay this deployment's business.

The previous docstring claimed the tiers were "configurable through the environment"
and they were not — the table was a hardcoded dict with no `os.getenv` anywhere near
it. `llmkit` implements `LLMKIT_ROUTE_<TIER>="provider:model"`, so the claim is now
true for anything llmkit resolves directly; routes passed in from here still come from
`core.config`.
"""

from llmkit.config import LLMConfig
from llmkit.routing import resolve as _resolve

from app.core.config import get_settings

__all__ = ["resolve"]


def resolve(tier: str) -> dict:
    """Return `{provider, model, temperature, tier}` for a tier, e.g. 'reasoning'.

    The returned dict gained a `tier` key in the extraction. It reports the tier
    actually used, which differs from the one requested when an unknown tier falls
    back to `reasoning` — so the fallback shows up in cost reporting rather than
    masquerading as the tier that was asked for. Existing callers unpack `provider`,
    `model`, and `temperature` and are unaffected by the extra key.
    """
    settings = get_settings()
    return _resolve(tier, config=LLMConfig(routes=settings.default_routes))
