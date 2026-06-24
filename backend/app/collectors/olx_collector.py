"""
OLX.kz public listings collector.
Scrapes search results for configured keywords, respects rate limits.

Required env vars:
  OLX_KEYWORDS — comma-separated keywords (default provided)
"""
import json
import logging
import time
from datetime import datetime, timezone
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

from app.collectors.base import BaseCollector, RawPostData
from app.config import settings

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
BASE_URL = "https://www.olx.kz"
RATE_LIMIT_SEC = 3


class OlxCollector(BaseCollector):
    def __init__(self, max_per_keyword: int = 40):
        self._max = max_per_keyword
        self._keywords = [k.strip() for k in settings.olx_keywords.split(",") if k.strip()]
        self._session = requests.Session()
        self._session.headers.update(HEADERS)

    def fetch(self) -> list[RawPostData]:
        results: list[RawPostData] = []
        for keyword in self._keywords:
            try:
                batch = self._fetch_keyword(keyword)
                results.extend(batch)
                logger.info(f"OLX: '{keyword}' → {len(batch)} listings")
            except Exception as e:
                logger.error(f"OLX error for '{keyword}': {e}")
            time.sleep(RATE_LIMIT_SEC)
        logger.info(f"OlxCollector total: {len(results)} listings")
        return results

    def _fetch_keyword(self, keyword: str) -> list[RawPostData]:
        # /list/q-{keyword}/ is the working search URL on olx.kz
        url = f"{BASE_URL}/list/q-{quote(keyword)}/"
        resp = self._session.get(url, timeout=20)
        if resp.status_code != 200:
            logger.warning(f"OLX: HTTP {resp.status_code} for '{keyword}'")
            return []

        # Try embedded Next.js JSON first (fastest, most data)
        try:
            return self._parse_next_data(resp.text, keyword)
        except Exception:
            pass

        # Fall back to HTML scraping
        return self._parse_html(resp.text, keyword)

    def _parse_next_data(self, html: str, keyword: str) -> list[RawPostData]:
        soup = BeautifulSoup(html, "lxml")
        tag = soup.find("script", id="__NEXT_DATA__")
        if not tag or not tag.string:
            raise ValueError("No __NEXT_DATA__")

        data = json.loads(tag.string)
        # OLX Next.js structure (may vary by version)
        ads = (
            data.get("props", {})
                .get("pageProps", {})
                .get("data", {})
                .get("ads", [])
        )
        if not ads:
            raise ValueError("No ads in __NEXT_DATA__")

        results = []
        for ad in ads[:self._max]:
            title = ad.get("title", "").strip()
            description = ad.get("description", "").strip()
            text = f"{title}\n{description}".strip() if description else title
            if not text:
                continue
            ad_url = ad.get("url", "")
            if ad_url and not ad_url.startswith("http"):
                ad_url = BASE_URL + ad_url
            results.append(RawPostData(
                source=f"olx:{keyword}",
                text=text,
                external_id=f"olx_{ad.get('id', '')}",
                source_url=ad_url or None,
                collected_at=datetime.now(timezone.utc),
                raw={"keyword": keyword, "title": title, "ad_id": ad.get("id")},
            ))
        return results

    def _parse_html(self, html: str, keyword: str) -> list[RawPostData]:
        soup = BeautifulSoup(html, "lxml")
        results = []

        # OLX card selectors (stable data-cy attributes)
        cards = soup.select("[data-cy='l-card']")
        if not cards:
            # Fallback: any card-like element
            cards = soup.select("li[data-testid], div[data-id]")

        for card in cards[:self._max]:
            title_el = (
                card.select_one("[data-cy='ad-card-title']")
                or card.select_one("h6")
                or card.select_one("h4")
                or card.select_one("strong")
            )
            title = title_el.get_text(strip=True) if title_el else ""
            if not title:
                continue

            # Price adds context for the classifier
            price_el = card.select_one("[data-testid='ad-price']")
            price = price_el.get_text(strip=True) if price_el else ""

            # Location/description snippet
            desc_el = card.select_one("[data-testid='location-date']") or card.select_one("p")
            desc = desc_el.get_text(strip=True) if desc_el else ""

            text = title
            if price:
                text += f"\n{price}"
            if desc:
                text += f"\n{desc}"

            link_el = card.select_one("a[href]")
            ad_url = link_el["href"] if link_el else ""
            if ad_url and ad_url.startswith("/"):
                ad_url = BASE_URL + ad_url

            ad_id = card.get("id", "") or card.get("data-id", "") or ad_url

            results.append(RawPostData(
                source=f"olx:{keyword}",
                text=text,
                external_id=f"olx_{ad_id}" if ad_id else None,
                source_url=ad_url or None,
                collected_at=datetime.now(timezone.utc),
                raw={"keyword": keyword, "title": title, "price": price},
            ))
        return results
