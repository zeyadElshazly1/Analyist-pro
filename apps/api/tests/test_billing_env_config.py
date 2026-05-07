"""
80B — Billing env-var configuration tests.

Verifies that:
- STRIPE_CONSULTANT_PRICE_ID and STRIPE_STUDIO_PRICE_ID are the only
  canonical env vars used to configure checkout price IDs.
- Legacy env vars STRIPE_PRO_PRICE_ID / STRIPE_TEAM_PRICE_ID no longer
  configure price IDs (removing silent drift risk on deploy).
- Legacy plan-name aliases in API requests ("pro", "team") are still
  normalised by normalize_plan and reach the correct canonical plan.
"""
from __future__ import annotations

import importlib
import os
import sys


def _reload_billing(env: dict) -> object:
    """Reload billing module with a patched environment."""
    old = {k: os.environ.get(k) for k in env}
    for k, v in env.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    # Remove cached module so os.getenv calls re-execute at module level.
    sys.modules.pop("app.routes.billing", None)
    try:
        mod = importlib.import_module("app.routes.billing")
        return mod
    finally:
        # Restore env
        for k, orig in old.items():
            if orig is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = orig
        sys.modules.pop("app.routes.billing", None)


class TestStripeEnvVarCanonical:
    def test_canonical_consultant_price_id_used(self):
        mod = _reload_billing({"STRIPE_CONSULTANT_PRICE_ID": "price_cons_123"})
        assert "price_cons_123" in mod.STRIPE_PLAN_MAP
        assert mod.STRIPE_PLAN_MAP["price_cons_123"] == "consultant"

    def test_canonical_studio_price_id_used(self):
        mod = _reload_billing({"STRIPE_STUDIO_PRICE_ID": "price_studio_456"})
        assert "price_studio_456" in mod.STRIPE_PLAN_MAP
        assert mod.STRIPE_PLAN_MAP["price_studio_456"] == "studio"

    def test_legacy_pro_price_id_not_used(self):
        """STRIPE_PRO_PRICE_ID alone must not configure any price."""
        mod = _reload_billing({
            "STRIPE_PRO_PRICE_ID": "price_legacy_pro",
            "STRIPE_CONSULTANT_PRICE_ID": None,
        })
        assert "price_legacy_pro" not in mod.STRIPE_PLAN_MAP

    def test_legacy_team_price_id_not_used(self):
        """STRIPE_TEAM_PRICE_ID alone must not configure any price."""
        mod = _reload_billing({
            "STRIPE_TEAM_PRICE_ID": "price_legacy_team",
            "STRIPE_STUDIO_PRICE_ID": None,
        })
        assert "price_legacy_team" not in mod.STRIPE_PLAN_MAP

    def test_plan_price_map_uses_canonical_consultant(self):
        mod = _reload_billing({"STRIPE_CONSULTANT_PRICE_ID": "price_cons_789"})
        from app.plan_names import PLAN_CONSULTANT
        assert mod._PLAN_PRICE_MAP[PLAN_CONSULTANT] == "price_cons_789"

    def test_plan_price_map_uses_canonical_studio(self):
        mod = _reload_billing({"STRIPE_STUDIO_PRICE_ID": "price_studio_789"})
        from app.plan_names import PLAN_STUDIO
        assert mod._PLAN_PRICE_MAP[PLAN_STUDIO] == "price_studio_789"

    def test_plan_price_map_empty_without_canonical_env(self):
        """Without canonical env vars, price IDs should be empty strings (not legacy values)."""
        mod = _reload_billing({
            "STRIPE_CONSULTANT_PRICE_ID": None,
            "STRIPE_STUDIO_PRICE_ID": None,
            "STRIPE_PRO_PRICE_ID": "should_not_appear",
            "STRIPE_TEAM_PRICE_ID": "should_not_appear",
        })
        from app.plan_names import PLAN_CONSULTANT, PLAN_STUDIO
        assert mod._PLAN_PRICE_MAP[PLAN_CONSULTANT] == ""
        assert mod._PLAN_PRICE_MAP[PLAN_STUDIO] == ""


class TestLegacyPlanNameAlias:
    """Legacy plan-name aliases in request bodies must still normalize correctly."""

    def test_normalize_plan_pro_to_consultant(self):
        from app.plan_names import normalize_plan
        assert normalize_plan("pro") == "consultant"

    def test_normalize_plan_team_to_studio(self):
        from app.plan_names import normalize_plan
        assert normalize_plan("team") == "studio"

    def test_normalize_plan_canonical_passthrough(self):
        from app.plan_names import normalize_plan
        assert normalize_plan("consultant") == "consultant"
        assert normalize_plan("studio") == "studio"
        assert normalize_plan("free") == "free"
