"""
Stub for future public source collectors (Telegram public channels, OLX, etc.).
Only enabled when USE_PUBLIC_SOURCES=true. Never connects to illegal sources.
"""
import logging
from app.collectors.base import BaseCollector, RawPostData

logger = logging.getLogger(__name__)


class PublicStubCollector(BaseCollector):
    """Skeleton for public-source collection. Not active in MVP."""

    def fetch(self) -> list[RawPostData]:
        logger.debug("PublicStubCollector: no-op in MVP")
        return []
