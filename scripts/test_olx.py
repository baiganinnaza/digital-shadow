"""Quick OLX collector pipeline smoke test."""
import sys, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("MODEL_PATH", "ml/models/clf.joblib")
os.environ.setdefault("WALLET_BLACKLIST_PATH", "data/wallet_blacklist.txt")
os.environ["OLX_KEYWORDS"] = "вейп,жижа"

from app.collectors.olx_collector import OlxCollector

c = OlxCollector(max_per_keyword=5)
posts = c.fetch()
print(f"\nFetched {len(posts)} OLX listings")
for p in posts:
    print(f"  [{p.source}] id={p.external_id}")
    print(f"    text={p.text[:80].encode('utf-8').decode('utf-8')}")
    print(f"    url={p.source_url}")
    print()
