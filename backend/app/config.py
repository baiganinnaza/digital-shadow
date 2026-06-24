from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://shadow:shadow@localhost:5432/digital_shadow"
    redis_url: str = "redis://localhost:6379/0"
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "shadowpass"
    use_local_llm: bool = False
    collect_interval_sec: int = 60
    seed_file_path: str = "data/seed_posts.jsonl"
    wallet_blacklist_path: str = "data/wallet_blacklist.txt"
    model_path: str = "ml/models/clf.joblib"

    # Public source collectors
    use_public_sources: bool = False

    # Telegram (Telethon)
    tg_api_id: str = ""
    tg_api_hash: str = ""
    tg_channels: str = ""          # comma-separated: @channel1,@channel2
    tg_session_path: str = "data/tg_session"
    tg_lookback_hours: int = 24

    # OLX.kz
    olx_keywords: str = "вейп,жижа,испаритель,алкоголь оптом,дроп,курьер анон,нал доставка"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
