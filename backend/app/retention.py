"""Prune old chat content while preserving open and recent moderation evidence."""
from datetime import timedelta

from sqlalchemy import delete, select

from .models import ChatMessage, ChatReport, now


def prune_chat(factory, mutation_lock, retention_days: int):
    message_cutoff = now() - timedelta(days=retention_days)
    report_cutoff = now() - timedelta(days=max(retention_days, 365))
    with mutation_lock, factory() as db:
        db.execute(delete(ChatReport).where(ChatReport.status != 'OPEN', ChatReport.reviewed_at < report_cutoff))
        protected = select(ChatReport.message_id)
        db.execute(delete(ChatMessage).where(ChatMessage.created_at < message_cutoff,
                   ChatMessage.id.not_in(protected)))
        db.commit()
