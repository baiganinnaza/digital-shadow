"""
Generates synthetic data for training and demo.
Outputs:
  data/seed_posts.jsonl  (~150 posts for demo)
  data/labeled.jsonl     (~300 labeled examples for training)
  data/wallet_blacklist.txt
"""
import json
import random
import string
from pathlib import Path

random.seed(42)

# ── Фейковые идентификаторы ──────────────────────────────────────────────────

def fake_btc():
    chars = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz"
    return "bc1q" + "".join(random.choices(chars[:32], k=38))

def fake_eth():
    return "0x" + "".join(random.choices("0123456789abcdef", k=40))

def fake_tron():
    chars = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz"
    return "T" + "".join(random.choices(chars, k=33))

def fake_phone():
    return f"+7 ({random.randint(700,799)}) {random.randint(100,999)}-{random.randint(10,99)}-{random.randint(10,99)}"

def fake_user(n):
    return f"@demo_user_{n:02d}"

def fake_channel(n):
    return f"@demo_channel_{n:02d}"

# ── Предзаданные объекты для кластера (главный демо-кластер) ─────────────────

CLUSTER_WALLET_BTC = "bc1qcluster0000000000000000000000000000demo"
CLUSTER_WALLET_ETH = "0xDEAD000000000000000000000000000000000001"
CLUSTER_USER_A     = "@demo_user_01"
CLUSTER_USER_B     = "@demo_user_02"
CLUSTER_CHANNEL    = "@demo_channel_01"
CLUSTER_PHONE      = "+7 (777) 001-01-01"

BLACKLISTED_WALLETS = [
    CLUSTER_WALLET_BTC,
    "bc1qblack0000000000000000000000000000000bad",
    fake_btc(),
    fake_btc(),
    fake_eth(),
]

# ── Шаблоны постов ───────────────────────────────────────────────────────────

VAPES_SALE = [
    "Продаю жижу оптом, любые вкусы. ТГ: {user}. Оплата {wallet}",
    "Вейп жидкость прод, опт от 10 флаконов. Пиши {user} цена договорная",
    "Прод испаритель б/у + 5 флаконов жижи. {user} {phone}",
    "Оптовые поставки вейп расходников. Канал {channel}, кошель {wallet}",
    "Купить жижу недорого, Алматы. {user} пишите в лс. {wallet}",
    "Vape жижа оптом RU/KZ. Тг {user}. btc {wallet}",
    "Распродаю коллекцию испарителей. {user}, {channel}. Принимаем {wallet}",
    "Продам под никотиновые соли. {user}. Доставка по РК. {phone}",
]

VAPES_DISCUSS = [
    "Какой испаритель лучше для солевого никотина? Посоветуйте",
    "Обсуждаем вкусы жиж — какой ваш любимый?",
    "Кто пробовал новые под-системы? Делитесь впечатлениями",
    "Переехал на механические моды, всем советую",
    "Сравниваем Suorin и Vaporesso — что лучше?",
]

ALCOHOL_SALE = [
    "Продам алкоголь оптом без акциза. {user} {phone}",
    "Нелегальный алкоголь дёшево. Пишите {user}, оплата {wallet}",
    "Самогон домашний, очищенный. {phone} звоните",
    "Палёнка оптом, вся РК. {channel} {user}",
    "Продаю без чека. {user} тг. {wallet}",
]

ALCOHOL_DISCUSS = [
    "Какое вино лучше брать на новый год?",
    "Обсуждение крафтового пива в Алматы",
    "Рецепт домашнего вина из винограда",
]

DRUGS_SALE = [
    "Прод товар, оплата крипта {wallet}. {user}",
    "Есть в наличии, доставка закладками. Пишите {user}",
    "Работаем по РК, ТГ {user}. ETH {wallet}",
    "Магазин открылся, актуальный прайс у {user}. {channel}",
    "Закладки по городу. {user} {wallet}",
    "Оптовые объёмы, крипта обязательна. {wallet} {user}",
]

LEAK_POSTS = [
    "Слив базы клиентов банка РК, 500к записей. {user} {wallet}",
    "Продаю базу данных ЕГКНТ, свежая. {user} цена {wallet}",
    "Утечка базы ЦОН. {user} telegram. {wallet}",
    "Сливаю базу мобильного оператора. Писать {user}",
    "База ЕНПФ 2024 года, полная. {user} btc {wallet}",
]

NONE_POSTS = [
    "Хорошая погода сегодня в Алматы",
    "Новый кофейный сорт в нашем кафе — приходите!",
    "Ищу репетитора по математике для 8 класса",
    "Продаю велосипед, Алматы, хорошее состояние {phone}",
    "Кто порекомендует хорошего стоматолога?",
    "Ищу работу программистом, опыт 3 года",
    "Сдаю квартиру в Нур-Султане, 2 комнаты",
    "Продаю книги по психологии, недорого",
    "Щенки лабрадора, 2 месяца, ищут дом",
    "Открылся новый фитнес-клуб на Абая",
    "Куплю смартфон б/у, бюджет 50к тенге",
    "Репетитор английского языка, сертификат IELTS",
    "Продаю детскую коляску, состояние отличное",
    "Ищу попутчиков Алматы–Астана на выходных",
    "Компьютерный мастер, выезд на дом {phone}",
]

# ── Вспомогательные функции ──────────────────────────────────────────────────

def fill_template(template: str, wallets: list, users: list, channels: list, phones: list) -> str:
    w = random.choice(wallets) if wallets else fake_btc()
    u = random.choice(users) if users else fake_user(random.randint(10, 99))
    c = random.choice(channels) if channels else fake_channel(random.randint(10, 99))
    p = random.choice(phones) if phones else fake_phone()
    return (template
            .replace("{wallet}", w)
            .replace("{user}", u)
            .replace("{channel}", c)
            .replace("{phone}", p))

def augment(text: str) -> str:
    replacements = {
        "продаю": ["прод", "продам", "прoдаю", "пр0даю"],
        "купить": ["куп", "купи", "куплю"],
        "доставка": ["дост", "доставлю", "д0ставка"],
        "оплата": ["оплат", "оплачу", "оплт"],
        "telegram": ["тг", "тлг", "телега"],
        "оптом": ["опт", "оптовых", "оптовый"],
    }
    for word, variants in replacements.items():
        if word in text.lower() and random.random() < 0.3:
            text = text.lower().replace(word, random.choice(variants), 1)
    if random.random() < 0.2:
        emojis = ["🔥", "✅", "💰", "📦", "👇", "💊", "🚀"]
        text = text + " " + random.choice(emojis)
    return text

# ── Основная генерация ───────────────────────────────────────────────────────

def generate_posts(n_extra_wallets: int = 8):
    extra_wallets = [fake_btc() for _ in range(n_extra_wallets // 2)] + \
                    [fake_eth() for _ in range(n_extra_wallets // 2)]
    extra_users = [fake_user(i) for i in range(3, 30)]
    extra_channels = [fake_channel(i) for i in range(2, 15)]
    extra_phones = [fake_phone() for _ in range(10)]

    posts = []

    # ── Демо-кластер: 5 постов с одним BTC-кошельком и одними участниками ──
    cluster_posts = [
        {
            "text": f"Продаю жижу оптом. {CLUSTER_USER_A} принимаем {CLUSTER_WALLET_BTC} {CLUSTER_CHANNEL}",
            "category": "vapes", "is_illegal_sale": True, "intent": "sale",
            "source": "seed:telegram",
        },
        {
            "text": f"Оптовые поставки. Пишите {CLUSTER_USER_B}. BTC: {CLUSTER_WALLET_BTC}",
            "category": "vapes", "is_illegal_sale": True, "intent": "sale",
            "source": "seed:telegram",
        },
        {
            "text": f"Закладки по городу. {CLUSTER_USER_A}. Оплата крипта {CLUSTER_WALLET_BTC}",
            "category": "drugs", "is_illegal_sale": True, "intent": "sale",
            "source": "seed:darknet",
        },
        {
            "text": f"Дроп ищет работу. {CLUSTER_USER_B} в тг. Кошель {CLUSTER_WALLET_BTC}",
            "category": "drugs", "is_illegal_sale": True, "intent": "ad",
            "source": "seed:darknet",
        },
        {
            "text": f"Слив базы ЕГКНТ. {CLUSTER_USER_A} btc {CLUSTER_WALLET_BTC} {CLUSTER_PHONE}",
            "category": "leak", "is_illegal_sale": True, "intent": "sale",
            "source": "seed:forum",
        },
    ]
    posts.extend(cluster_posts)

    # ── ETH-кластер: 3 поста с CLUSTER_WALLET_ETH ──
    eth_cluster = [
        {
            "text": f"Алкоголь без акциза оптом. {CLUSTER_USER_B} eth {CLUSTER_WALLET_ETH} {CLUSTER_PHONE}",
            "category": "alcohol", "is_illegal_sale": True, "intent": "sale",
            "source": "seed:olx",
        },
        {
            "text": f"Паль опт. {CLUSTER_CHANNEL} eth {CLUSTER_WALLET_ETH}",
            "category": "alcohol", "is_illegal_sale": True, "intent": "sale",
            "source": "seed:telegram",
        },
        {
            "text": f"Продам товар, eth {CLUSTER_WALLET_ETH}. {CLUSTER_USER_A}",
            "category": "drugs", "is_illegal_sale": True, "intent": "sale",
            "source": "seed:darknet",
        },
    ]
    posts.extend(eth_cluster)

    def make_posts(templates, category, is_illegal, intent, n, wallets, users, channels, phones, source="seed:telegram"):
        for _ in range(n):
            t = augment(fill_template(random.choice(templates), wallets, users, channels, phones))
            posts.append({
                "text": t,
                "category": category,
                "is_illegal_sale": is_illegal,
                "intent": intent,
                "source": source,
            })

    make_posts(VAPES_SALE, "vapes", True, "sale", 18, extra_wallets, extra_users, extra_channels, extra_phones)
    make_posts(VAPES_DISCUSS, "vapes", False, "discussion", 12, [], extra_users, extra_channels, extra_phones)
    make_posts(ALCOHOL_SALE, "alcohol", True, "sale", 15, extra_wallets, extra_users, extra_channels, extra_phones, "seed:olx")
    make_posts(ALCOHOL_DISCUSS, "alcohol", False, "discussion", 8, [], extra_users, extra_channels, extra_phones)
    make_posts(DRUGS_SALE, "drugs", True, "sale", 20, extra_wallets, extra_users, extra_channels, extra_phones, "seed:darknet")
    make_posts(LEAK_POSTS, "leak", True, "sale", 12, extra_wallets, extra_users, extra_channels, extra_phones, "seed:forum")
    make_posts(NONE_POSTS, "none", False, "none", 40, [], extra_users, extra_channels, extra_phones, "seed:public")

    random.shuffle(posts)
    return posts


def write_jsonl(path: Path, records: list):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"Written {len(records)} records -> {path}")


def main():
    posts = generate_posts()

    # seed_posts.jsonl — для демо (добавляем external_id и source_url)
    seed = []
    for i, p in enumerate(posts):
        seed.append({
            "external_id": f"seed_{i:04d}",
            "source": p["source"],
            "source_url": None,
            "text": p["text"],
            "category": p["category"],
            "is_illegal_sale": p["is_illegal_sale"],
            "intent": p["intent"],
        })
    write_jsonl(Path("data/seed_posts.jsonl"), seed)

    # labeled.jsonl — для обучения (берём все + генерируем ещё)
    labeled = [{"text": p["text"], "category": p["category"],
                "is_illegal_sale": p["is_illegal_sale"], "intent": p["intent"]}
               for p in posts]
    # Дополнительный батч для обучения
    extra = generate_posts(n_extra_wallets=6)
    for p in extra:
        labeled.append({"text": p["text"], "category": p["category"],
                         "is_illegal_sale": p["is_illegal_sale"], "intent": p["intent"]})
    random.shuffle(labeled)
    write_jsonl(Path("data/labeled.jsonl"), labeled)

    # wallet_blacklist.txt
    blacklist_path = Path("data/wallet_blacklist.txt")
    blacklist_path.write_text("\n".join(BLACKLISTED_WALLETS) + "\n", encoding="utf-8")
    print(f"Written {len(BLACKLISTED_WALLETS)} wallets -> {blacklist_path}")


if __name__ == "__main__":
    main()
