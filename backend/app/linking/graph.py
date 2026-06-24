"""
Neo4j graph operations. All writes are idempotent via MERGE.
"""
import logging
from neo4j import Session

logger = logging.getLogger(__name__)


def upsert_node(session: Session, key: str, node_type: str, risk: float = 0.0):
    session.run(
        "MERGE (o:Object {key: $key}) "
        "ON CREATE SET o.type = $type, o.risk = $risk "
        "ON MATCH SET o.type = $type",
        key=key, type=node_type, risk=risk,
    )


def upsert_edge(session: Session, src_key: str, dst_key: str, rel_type: str, props: dict):
    safe_type = rel_type.upper().replace(" ", "_")
    allowed = {"PAYS_TO", "LINKED", "SAME_AS", "POSTED_IN"}
    if safe_type not in allowed:
        logger.warning(f"Unknown rel_type: {safe_type}")
        return

    reason = props.get("reason", "")
    confidence = props.get("confidence", 1.0)

    session.run(
        f"MERGE (a:Object {{key: $src}}) "
        f"MERGE (b:Object {{key: $dst}}) "
        f"MERGE (a)-[r:{safe_type}]->(b) "
        f"ON CREATE SET r.reason = $reason, r.confidence = $confidence",
        src=src_key, dst=dst_key, reason=reason, confidence=confidence,
    )


def update_node_risk(session: Session, key: str, risk: float):
    session.run(
        "MATCH (o:Object {key: $key}) SET o.risk = $risk",
        key=key, risk=risk,
    )


def link_shared_wallets(session: Session, wallet_key: str, account_keys: list[str]):
    """Links all accounts that share the same wallet via LINKED edges."""
    for account_key in account_keys:
        upsert_edge(session, account_key, wallet_key, "PAYS_TO", {"reason": "shared_wallet"})

    # Cross-link accounts to each other via shared wallet
    for i, a1 in enumerate(account_keys):
        for a2 in account_keys[i + 1:]:
            upsert_edge(session, a1, a2, "LINKED", {"reason": "shared_wallet", "confidence": 0.9})
