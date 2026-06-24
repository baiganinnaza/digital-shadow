import re
from dataclasses import dataclass


@dataclass
class ExtractedEntity:
    type: str
    value: str
    confidence: float = 1.0


_BTC = re.compile(r'\b(bc1[a-zA-HJ-NP-Z0-9]{25,39}|[13][a-zA-HJ-NP-Z0-9]{25,34})\b')
_ETH = re.compile(r'\b(0x[0-9a-fA-F]{40})\b')
_TRON = re.compile(r'\b(T[1-9A-HJ-NP-Za-km-z]{33})\b')
_PHONE = re.compile(r'(\+?7[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2})')
_USERNAME = re.compile(r'(@[a-zA-Z0-9_]{3,32})')
_PRICE = re.compile(r'(\d[\d\s]{0,6}(?:тг|тенге|руб|₸|₽|usd|\$))', re.IGNORECASE)

_KEYWORDS = re.compile(
    r'\b(продаю|продам|прод|закладк|дроп|слив|утечка|нарк|крипта|оплата|опт|жижа|вейп|алкоголь|самогон)\b',
    re.IGNORECASE,
)


def extract(text: str) -> list[ExtractedEntity]:
    results: list[ExtractedEntity] = []

    for m in _BTC.finditer(text):
        results.append(ExtractedEntity(type="wallet", value=m.group(1), confidence=0.99))

    for m in _ETH.finditer(text):
        results.append(ExtractedEntity(type="wallet", value=m.group(1).lower(), confidence=0.99))

    for m in _TRON.finditer(text):
        results.append(ExtractedEntity(type="wallet", value=m.group(1), confidence=0.95))

    for m in _PHONE.finditer(text):
        normalized = re.sub(r'[\s\-\(\)]', '', m.group(1))
        results.append(ExtractedEntity(type="phone", value=normalized, confidence=0.90))

    for m in _USERNAME.finditer(text):
        results.append(ExtractedEntity(type="username", value=m.group(1).lower(), confidence=1.0))

    for m in _PRICE.finditer(text):
        results.append(ExtractedEntity(type="price", value=m.group(1).strip(), confidence=0.85))

    seen = set()
    unique = []
    for e in results:
        key = (e.type, e.value)
        if key not in seen:
            seen.add(key)
            unique.append(e)

    return unique
