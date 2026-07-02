"""Model routing: resolve a task tier to a concrete (provider, model, params).

The model_routes table is the source of truth and is editable in the data admin;
config.default_routes is the fallback when a tier has no row.
"""
from app.core.config import get_settings
from app.db.session import query


def resolve(tier: str) -> dict:
    """Return {provider, model, temperature} for a tier (e.g. 'reasoning')."""
    rows = query(
        "SELECT provider, model_id, temperature FROM model_routes "
        "WHERE tier = %s AND active LIMIT 1",
        (tier,),
    )
    if rows:
        r = rows[0]
        return {
            "provider": r["provider"],
            "model": r["model_id"],
            "temperature": float(r["temperature"]) if r["temperature"] is not None else 0.2,
        }
    provider, model = get_settings().default_routes.get(
        tier, get_settings().default_routes["reasoning"]
    )
    return {"provider": provider, "model": model, "temperature": 0.2}
