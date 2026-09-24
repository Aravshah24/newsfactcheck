from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Table, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


evidence_cluster_members = Table(
    "evidence_cluster_members",
    Base.metadata,
    Column("evidence_item_id", ForeignKey("evidence_items.id"), primary_key=True),
    Column("evidence_cluster_id", ForeignKey("evidence_clusters.id"), primary_key=True),
)


class EvidenceCluster(Base):
    __tablename__ = "evidence_clusters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    claim_id: Mapped[int] = mapped_column(ForeignKey("claims.id"), nullable=False, index=True)
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    clustering_method: Mapped[str | None] = mapped_column(String(128), nullable=True)
    similarity_score: Mapped[float | None] = mapped_column(default=None, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    claim: Mapped["Claim"] = relationship(back_populates="evidence_clusters")
    evidence_items: Mapped[list["EvidenceItem"]] = relationship(
        back_populates="clusters",
        secondary=evidence_cluster_members,
    )
