"""Maps a channel identity (WhatsApp phone / Telegram chat_id) to a loyalty internal_user.

The encrypted_refresh_token is obtained from the loyalty core at binding time
and used to mint fresh access tokens before every mutation, so that the
loyalty audit trail records the real user, not the agent's service account.
"""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Text, UniqueConstraint, func, String
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ChannelIdentityBinding(Base):
    __tablename__ = "channel_identity_bindings"

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    channel_user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    company_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    internal_user_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    internal_user_email: Mapped[str] = mapped_column(String(255), nullable=False)
    internal_user_role: Mapped[str] = mapped_column(String(32), nullable=False)
    encrypted_refresh_token: Mapped[str] = mapped_column(Text, nullable=False)
    bound_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("channel", "channel_user_id", name="uq_channel_identity"),
    )
