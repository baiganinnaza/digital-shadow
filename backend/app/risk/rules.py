"""
Risk scoring: rule-based + ML signal.
All scores are explainable via reasons[].
"""
import logging
import yaml
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models import Entity, Object, RiskSignal
from app.config import settings

logger = logging.getLogger(__name__)

_CONFIG: dict | None = None
_BLACKLIST: set[str] | None = None


def _load_config() -> dict:
    global _CONFIG
    if _CONFIG is None:
        rules_path = Path(__file__).parent / "risk_rules.yaml"
        with rules_path.open() as f:
            _CONFIG = yaml.safe_load(f)
    return _CONFIG


def _load_blacklist() -> set[str]:
    global _BLACKLIST
    if _BLACKLIST is None:
        bl_path = Path(settings.wallet_blacklist_path)
        if bl_path.exists():
            _BLACKLIST = {line.strip() for line in bl_path.read_text().splitlines() if line.strip()}
        else:
            logger.warning(f"Wallet blacklist not found: {bl_path}")
            _BLACKLIST = set()
    return _BLACKLIST


async def calculate_risk(
    db: AsyncSession,
    obj: Object,
    entities: list[Entity],
    clf_result: dict,
) -> dict:
    config = _load_config()
    blacklist = _load_blacklist()
    weights = config["weights"]

    triggered: list[dict] = []

    # Rule 1: illegal_sale_detected (from classifier)
    if clf_result.get("is_illegal_sale"):
        triggered.append({"rule": "illegal_sale_detected", "weight": weights["illegal_sale_detected"]})

    # Rule 2: wallet_in_blacklist
    if obj.type == "wallet" and obj.key in blacklist:
        triggered.append({"rule": "wallet_in_blacklist", "weight": weights["wallet_in_blacklist"]})
    else:
        for e in entities:
            if e.type == "wallet" and e.value in blacklist:
                triggered.append({"rule": "wallet_in_blacklist", "weight": weights["wallet_in_blacklist"]})
                break

    # Rule 3: new_account (object just created, no prior signals)
    prior_result = await db.execute(
        select(func.count()).where(RiskSignal.object_id == obj.id)
    )
    prior_count = prior_result.scalar() or 0
    if prior_count == 0 and obj.type in ("account", "wallet"):
        triggered.append({"rule": "new_account", "weight": weights["new_account"]})

    # Rule 4: linked_to_flagged (object has attrs linking to known bad wallets)
    linked_accounts = obj.attrs.get("linked_accounts", [])
    if linked_accounts:
        for acc_key in linked_accounts:
            flagged_result = await db.execute(
                select(RiskSignal)
                .join(Object, RiskSignal.object_id == Object.id)
                .where(Object.key == acc_key, RiskSignal.score >= config["threshold"])
                .limit(1)
            )
            if flagged_result.scalar_one_or_none():
                triggered.append({"rule": "linked_to_flagged", "weight": weights["linked_to_flagged"]})
                break

    # Rule 5: multiple_listings (same object appears in many posts)
    listing_result = await db.execute(
        select(func.count()).select_from(Entity).where(Entity.value == obj.key)
    )
    listing_count = listing_result.scalar() or 0
    if listing_count >= 3:
        triggered.append({"rule": "multiple_listings", "weight": weights["multiple_listings"]})

    raw_score = sum(r["weight"] for r in triggered)
    score = min(max(raw_score, 0.0), 1.0)

    return {
        "score": score,
        "reasons": triggered,
        "flagged": score >= config["threshold"],
    }
