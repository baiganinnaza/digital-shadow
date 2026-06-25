"""
Keyword-based classifier for AML/OSINT signals.
No ML model required — rules cover KZ-specific criminal slang.
"""

PATTERNS: dict[str, dict] = {
    "наркотики": {
        "risk": "critical",
        "keywords": [
            "закладка", "клад", "тайник", "кладмен", "кладщик",
            "скорость", "мефедрон", "меф", "мет", "амфетамин",
            "героин", "гашиш", "гаш", "план", "шишки", "бошки",
            "соль", "фен", "кокаин", "крокодил", "экстази",
            "mdma", "мдма", "spice", "спайс", "pvp", "пвп",
            "альфа пвп", "a-pvp", "синтетика", "реагент",
            "lsd", "марки", "трип", "псилоц", "кристалл",
            "фасовка", "грамм цена", "опт розница", "доставка нарк",
        ],
    },
    "крипто_отмывание": {
        "risk": "high",
        "keywords": [
            "обнал", "обналичивание", "обнальщик",
            "обменять крипту", "p2p обмен", "otc обмен",
            "usdt нал", "btc нал", "eth нал",
            "вывод крипты", "нал за крипту", "крипта за нал",
            "миксер", "tumbler", "mixer", "blender",
            "анонимный обмен", "обмен без kyc", "без верификации",
        ],
    },
    "финансовое_мошенничество": {
        "risk": "high",
        "keywords": [
            "фишинг", "скам", "скамер",
            "кардинг", "кард", "cvv",
            "слив базы", "пробив", "пробить номер",
            "взлом аккаунта", "купить базу", "утечка данных",
            "поддельный документ", "фейк документ", "купить паспорт",
            "дамп карты", "скиммер",
        ],
    },
    "дропперство": {
        "risk": "high",
        "keywords": [
            "дроп нужен", "дроп ищу", "работа дропом",
            "дроппер", "дропер", "принять перевод",
            "принять деньги за %", "обналить карту",
            "карта прием", "карта для перевода", "мул",
        ],
    },
    "оружие": {
        "risk": "critical",
        "keywords": [
            "продаю ствол", "пистолет купить", "автомат продаю",
            "ak-47", "оружие без документов", "нелегальный ствол",
            "патроны оптом", "глушитель",
        ],
    },
    "торговля_людьми": {
        "risk": "critical",
        "keywords": [
            "работа за границей документы", "паспорт заберем",
            "перевезем нелегально", "без документов работа",
        ],
    },
}


class Classifier:
    _instance: "Classifier | None" = None

    @classmethod
    def get(cls) -> "Classifier":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def classify(self, text: str) -> dict:
        text_lower = text.lower()
        best_category: str = "легальный"
        best_risk: str = "low"
        is_illegal_sale: bool = False
        max_matches: int = 0

        for category, cfg in PATTERNS.items():
            hits = [kw for kw in cfg["keywords"] if kw in text_lower]
            if len(hits) > max_matches:
                max_matches = len(hits)
                best_category = category
                best_risk = cfg["risk"]
                is_illegal_sale = True

        confidence = min(max_matches * 0.25, 1.0)
        return {
            "category":       best_category,
            "risk":           best_risk,
            "is_illegal_sale": is_illegal_sale,
            "confidence":     confidence,
            "matches":        max_matches,
        }
