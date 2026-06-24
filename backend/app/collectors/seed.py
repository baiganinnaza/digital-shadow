import json
import logging
from pathlib import Path
from datetime import datetime, timezone

from app.collectors.base import BaseCollector, RawPostData
from app.config import settings

logger = logging.getLogger(__name__)


class SeedCollector(BaseCollector):
    def __init__(self, batch_size: int = 20):
        self._path = Path(settings.seed_file_path)
        self._batch_size = batch_size
        self._offset = 0
        self._posts: list[dict] = []
        self._load()

    def _load(self):
        if not self._path.exists():
            logger.warning(f"Seed file not found: {self._path}")
            return
        with self._path.open(encoding="utf-8") as f:
            self._posts = [json.loads(line) for line in f if line.strip()]
        logger.info(f"SeedCollector loaded {len(self._posts)} posts from {self._path}")

    def fetch(self) -> list[RawPostData]:
        if not self._posts:
            return []
        batch = self._posts[self._offset: self._offset + self._batch_size]
        self._offset = (self._offset + self._batch_size) % len(self._posts)
        result = []
        for p in batch:
            result.append(RawPostData(
                source=p.get("source", "seed:unknown"),
                text=p["text"],
                external_id=p.get("external_id"),
                source_url=p.get("source_url"),
                collected_at=datetime.now(timezone.utc),
                raw=p,
            ))
        return result
