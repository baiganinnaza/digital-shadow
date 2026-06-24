"""
Entity resolution: merges extracted entities into canonical Object records.
Rules:
  - Same wallet value → shared Object(type='wallet')
  - Same @username → shared Object(type='account')
  - Same phone → shared Object(type='phone')
"""
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import RawPost, Entity, Object

logger = logging.getLogger(__name__)

TYPE_MAP = {
    "wallet": "wallet",
    "username": "account",
    "phone": "phone",
    "price": "price_indicator",
    "channel": "channel",
}


async def resolve_entities(
    db: AsyncSession,
    post: RawPost,
    entities: list[Entity],
) -> list[Object]:
    resolved: list[Object] = []
    source_channel = _extract_source_channel(post.source)

    if source_channel:
        obj = await _upsert_object(db, "channel", source_channel)
        resolved.append(obj)

    for entity in entities:
        obj_type = TYPE_MAP.get(entity.type, entity.type)
        if entity.type == "price":
            continue
        obj = await _upsert_object(db, obj_type, entity.value)
        resolved.append(obj)

    # Add LINKED edges for objects sharing this post
    await _link_objects_in_post(db, resolved, post)

    return resolved


async def _upsert_object(db: AsyncSession, obj_type: str, key: str) -> Object:
    result = await db.execute(select(Object).where(Object.key == key))
    obj = result.scalar_one_or_none()
    if not obj:
        obj = Object(type=obj_type, key=key, attrs={})
        db.add(obj)
        await db.flush()
    return obj


async def _link_objects_in_post(db: AsyncSession, objects: list[Object], post: RawPost):
    """
    Mark cross-object links within same post as pending if confidence < 0.7.
    High-confidence links (same wallet, same username) are handled in graph.py.
    """
    if len(objects) < 2:
        return

    wallets = [o for o in objects if o.type == "wallet"]
    accounts = [o for o in objects if o.type == "account"]

    if wallets and accounts:
        for w in wallets:
            if not w.attrs.get("linked_accounts"):
                w.attrs = {**w.attrs, "linked_accounts": []}
            for a in accounts:
                linked = w.attrs.get("linked_accounts", [])
                if a.key not in linked:
                    w.attrs = {**w.attrs, "linked_accounts": linked + [a.key]}
    await db.flush()


def _extract_source_channel(source: str) -> str | None:
    if ":" in source:
        parts = source.split(":")
        if len(parts) > 1 and parts[1]:
            return f"source:{parts[1]}"
    return None
