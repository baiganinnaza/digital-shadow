from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


@dataclass
class RawPostData:
    source: str
    text: str
    external_id: Optional[str] = None
    source_url: Optional[str] = None
    collected_at: Optional[datetime] = None
    raw: dict = field(default_factory=dict)


class BaseCollector:
    def fetch(self) -> list[RawPostData]:
        raise NotImplementedError
