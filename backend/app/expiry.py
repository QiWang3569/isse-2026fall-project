"""Listing lifetimes; zero days means no deadline without changing legacy columns."""
from datetime import timedelta

from sqlalchemy import or_

from .models import now


def is_expired(record, instant=None):
    return record.validity_days != 0 and record.expires_at <= (instant or now())


def unexpired(model, instant=None):
    return or_(model.validity_days == 0, model.expires_at > (instant or now()))


def renew(record, validity_days=None, instant=None):
    if validity_days is not None:
        record.validity_days = validity_days
    record.expires_at = (instant or now()) + timedelta(days=record.validity_days)


def expiry_fields(record):
    return {'validity_days': record.validity_days,
            'expires_at': None if record.validity_days == 0 else record.expires_at.isoformat() + 'Z'}
