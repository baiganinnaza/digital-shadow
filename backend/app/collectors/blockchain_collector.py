"""
Blockchain transaction monitor.
Watches wallets extracted from posts: TRON (USDT TRC20), ETH, BTC.
Reports suspicious transactions back as RawPostData entries.
"""
import asyncio
import logging
from datetime import datetime, timezone

import httpx

from app.collectors.base import BaseCollector, RawPostData
from app.config import settings

logger = logging.getLogger(__name__)

TRON_API          = "https://api.trongrid.io/v1"
USDT_TRC20        = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"
USDT_ERC20        = "0xdAC17F958D2ee523a2206206994597C13D831ec7"
ETH_API           = "https://api.etherscan.io/api"
BTC_API           = "https://blockchain.info"
MIN_USDT_REPORT   = 500      # report TXs above this USDT amount
MIN_BTC_REPORT    = 0.005    # report TXs above this BTC amount
MAX_WALLETS_QUERY = 60       # wallets to check per cycle


class BlockchainCollector(BaseCollector):
    """Checks wallets seen in posts for suspicious on-chain activity.

    Wallet addresses must be supplied at construction time — the caller
    (scheduler) is responsible for loading them from the DB in the main
    async context so we never touch AsyncSessionLocal from a thread.
    """

    def __init__(self, wallets: list[str] | None = None):
        self._wallets = wallets or []

    def fetch(self) -> list[RawPostData]:
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(asyncio.run, self._async_fetch())
            try:
                return future.result(timeout=180)
            except Exception as e:
                logger.error(f"BlockchainCollector failed: {e}")
                return []

    async def _async_fetch(self) -> list[RawPostData]:
        wallets = self._wallets
        logger.info(f"BlockchainCollector: checking {len(wallets)} wallets")
        results: list[RawPostData] = []

        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            for addr in wallets:
                try:
                    if addr.startswith("T") and len(addr) == 34:
                        results.extend(await self._tron_usdt(client, addr))
                    elif addr.startswith("0x") and len(addr) == 42:
                        results.extend(await self._eth_usdt(client, addr))
                    elif addr[:1] in ("1", "3") or addr.startswith("bc1"):
                        results.extend(await self._btc(client, addr))
                    await asyncio.sleep(0.3)  # polite rate limit
                except Exception as e:
                    logger.debug(f"Blockchain skip {addr[:10]}…: {e}")

        logger.info(f"BlockchainCollector: {len(results)} transactions found")
        return results

    # ── TRON ─────────────────────────────────────────────────────────────────

    async def _tron_usdt(self, client: httpx.AsyncClient, addr: str) -> list[RawPostData]:
        url = f"{TRON_API}/accounts/{addr}/transactions/trc20"
        params = {"limit": 20, "contract_address": USDT_TRC20, "only_confirmed": "true"}
        resp = await client.get(url, params=params)
        if resp.status_code != 200:
            return []
        txns = resp.json().get("data", [])

        out: list[RawPostData] = []
        for tx in txns:
            try:
                amount = int(tx.get("value", "0")) / 1_000_000
                if amount < MIN_USDT_REPORT:
                    continue
                tx_hash   = tx.get("transaction_id", "")
                from_addr = tx.get("from", "")
                to_addr   = tx.get("to", "")
                risk_tag  = "🔴 КРУПНАЯ" if amount >= 5000 else "🟡"
                text = (
                    f"{risk_tag} TRON/USDT транзакция\n"
                    f"Сумма: ${amount:,.2f} USDT\n"
                    f"От: {from_addr}\n"
                    f"К: {to_addr}\n"
                    f"TX: {tx_hash}"
                )
                out.append(RawPostData(
                    source=f"blockchain:tron:{addr[:12]}",
                    text=text,
                    external_id=f"tron_{tx_hash}",
                    source_url=f"https://tronscan.org/#/transaction/{tx_hash}",
                    collected_at=datetime.now(timezone.utc),
                    raw={
                        "chain": "TRON", "token": "USDT-TRC20",
                        "amount_usdt": amount,
                        "from": from_addr, "to": to_addr,
                        "tx_hash": tx_hash, "watched_address": addr,
                    },
                ))
            except (ValueError, KeyError):
                continue
        return out

    # ── ETH ──────────────────────────────────────────────────────────────────

    async def _eth_usdt(self, client: httpx.AsyncClient, addr: str) -> list[RawPostData]:
        if not settings.etherscan_api_key:
            return []
        params = {
            "module": "account", "action": "tokentx",
            "address": addr, "contractaddress": USDT_ERC20,
            "page": 1, "offset": 10, "sort": "desc",
            "apikey": settings.etherscan_api_key,
        }
        resp = await client.get(ETH_API, params=params)
        txns = resp.json().get("result", [])
        if not isinstance(txns, list):
            return []

        out: list[RawPostData] = []
        for tx in txns:
            try:
                amount = int(tx["value"]) / 1_000_000
                if amount < MIN_USDT_REPORT:
                    continue
                tx_hash = tx.get("hash", "")
                text = (
                    f"ETH/USDT транзакция\n"
                    f"Сумма: ${amount:,.2f} USDT\n"
                    f"От: {tx.get('from','')}\n"
                    f"К: {tx.get('to','')}\n"
                    f"TX: {tx_hash}"
                )
                out.append(RawPostData(
                    source=f"blockchain:eth:{addr[:12]}",
                    text=text,
                    external_id=f"eth_{tx_hash}",
                    source_url=f"https://etherscan.io/tx/{tx_hash}",
                    collected_at=datetime.now(timezone.utc),
                    raw={"chain": "ETH", "token": "USDT-ERC20",
                         "amount_usdt": amount, "tx_hash": tx_hash, "watched_address": addr},
                ))
            except (ValueError, KeyError):
                continue
        return out

    # ── BTC ──────────────────────────────────────────────────────────────────

    async def _btc(self, client: httpx.AsyncClient, addr: str) -> list[RawPostData]:
        resp = await client.get(f"{BTC_API}/rawaddr/{addr}?limit=5")
        if resp.status_code != 200:
            return []
        txns = resp.json().get("txs", [])

        out: list[RawPostData] = []
        for tx in txns:
            try:
                received = sum(
                    o["value"] for o in tx.get("out", [])
                    if o.get("addr") == addr
                ) / 1e8
                if received < MIN_BTC_REPORT:
                    continue
                tx_hash = tx.get("hash", "")
                text = (
                    f"Bitcoin транзакция\n"
                    f"Получено: {received:.6f} BTC\n"
                    f"TX: {tx_hash}"
                )
                out.append(RawPostData(
                    source=f"blockchain:btc:{addr[:12]}",
                    text=text,
                    external_id=f"btc_{tx_hash}",
                    source_url=f"https://www.blockchain.com/btc/tx/{tx_hash}",
                    collected_at=datetime.now(timezone.utc),
                    raw={"chain": "BTC", "btc_amount": received,
                         "tx_hash": tx_hash, "watched_address": addr},
                ))
            except Exception:
                continue
        return out
