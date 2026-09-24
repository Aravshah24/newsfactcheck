from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    claim_id: Mapped[int] = mapped_column(ForeignKey("claims.id"), nullable=False, index=True)
    agent_name: Mapped[str] = mapped_column(String(128), nullable=False)
    run_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False)
    input_reference: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_reference: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra_metadata: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)

    claim: Mapped["Claim"] = relationship(back_populates="agent_runs")
    audit_events: Mapped[list["AuditEvent"]] = relationship(back_populates="agent_run", cascade="all, delete-orphan")
