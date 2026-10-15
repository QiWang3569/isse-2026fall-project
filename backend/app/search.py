"""Literal, case-insensitive keyword matching shared by items and wanted posts."""
from sqlalchemy import func, or_

from .services import FEATURES, normalize


def keyword_filters(query, *columns):
    # Every whitespace-separated term must match; aliases of one term are alternatives.
    for word in dict.fromkeys(query.lower().split()):
        normalized = normalize(word)
        aliases = {word, normalized, *FEATURES.get(normalized, [])} - {''}
        yield or_(*(func.lower(column).contains(alias.lower(), autoescape=True)
                    for column in columns for alias in aliases))
