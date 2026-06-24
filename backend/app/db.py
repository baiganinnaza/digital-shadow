from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from neo4j import GraphDatabase
from redis import Redis
from app.config import settings

engine = create_async_engine(settings.database_url, pool_pre_ping=True)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_neo4j_driver():
    return GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password),
    )


def get_redis() -> Redis:
    return Redis.from_url(settings.redis_url, decode_responses=True)


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
