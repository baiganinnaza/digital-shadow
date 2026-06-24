from datetime import datetime
from sqlalchemy import BigInteger, Text, REAL, TIMESTAMP, ForeignKey, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db import Base


class RawPost(Base):
    __tablename__ = "raw_posts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text)
    external_id: Mapped[str | None] = mapped_column(Text)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    collected_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
    raw: Mapped[dict | None] = mapped_column(JSONB)

    entities: Mapped[list["Entity"]] = relationship(back_populates="post")


class Entity(Base):
    __tablename__ = "entities"
    __table_args__ = (UniqueConstraint("post_id", "type", "value"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    post_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("raw_posts.id"))
    type: Mapped[str] = mapped_column(Text, nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(REAL, default=1.0)

    post: Mapped["RawPost"] = relationship(back_populates="entities")


class Object(Base):
    __tablename__ = "objects"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    type: Mapped[str] = mapped_column(Text, nullable=False)
    key: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    attrs: Mapped[dict] = mapped_column(JSONB, default=dict)

    signals: Mapped[list["RiskSignal"]] = relationship(back_populates="object")


class RiskSignal(Base):
    __tablename__ = "risk_signals"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    object_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("objects.id"))
    score: Mapped[float] = mapped_column(REAL, nullable=False)
    reasons: Mapped[list] = mapped_column(JSONB, nullable=False)
    category: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
    status: Mapped[str] = mapped_column(Text, default="open")

    object: Mapped["Object"] = relationship(back_populates="signals")
    feedbacks: Mapped[list["Feedback"]] = relationship(back_populates="signal")


class Case(Base):
    __tablename__ = "cases"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    object_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("objects.id"))
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())


class Feedback(Base):
    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    signal_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("risk_signals.id"))
    verdict: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())

    signal: Mapped["RiskSignal"] = relationship(back_populates="feedbacks")
