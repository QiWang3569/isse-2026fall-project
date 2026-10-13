"""One wanted post can own one independently managed watch task."""
from datetime import timedelta

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from .models import Base, Intent, now
from .services import FEATURES, log, model_name, parse_local


class WantedWatch(Base):
    __tablename__ = 'wanted_watches'
    wanted_id: Mapped[str] = mapped_column(ForeignKey('wanted_posts.id'), primary_key=True)
    intent_id: Mapped[str] = mapped_column(ForeignKey('buyer_intents.id'), unique=True)


def watch_conditions(wanted):
    raw = f'{wanted.title}，{wanted.description}'
    parsed = parse_local(raw)
    # Preserve uncommon product names while adding recognized required features.
    # Exclusions/preferences in the description must not turn its prose into a keyword.
    parsed.keywords = list(dict.fromkeys([
        *parse_local(wanted.title).keywords,
        *(word for word in parsed.keywords if word in FEATURES),
    ]))[:12]
    parsed.category = wanted.category
    parsed.campus = wanted.campus
    return parsed


def add_wanted_watch(db, wanted, user, parsed, vector, settings, validity_days, matching):
    task = Intent(buyer_id=user.id, raw_query=f'{wanted.title}，{wanted.description}'[:500],
                  category=wanted.category, max_price_cents=wanted.budget_cents,
                  campus=wanted.campus, keywords=parsed.keywords,
                  excluded_keywords=parsed.excluded_keywords, preferences=parsed.preferences,
                  condition_grade=parsed.condition_grade, embedding=vector,
                  embedding_model=model_name(settings), validity_days=validity_days,
                  expires_at=now() + timedelta(days=validity_days))
    db.add(task)
    db.flush()
    db.add(WantedWatch(wanted_id=wanted.id, intent_id=task.id))
    job_id = matching.enqueue(db, 'intent', task.id)
    log(db, user, 'wanted.watch', wanted.id, task.id)
    return job_id


def linked_watch(db, wanted, user):
    if not user or wanted.buyer_id != user.id:
        return None
    link = db.get(WantedWatch, wanted.id)
    task = db.get(Intent, link.intent_id) if link else None
    return task if task and task.buyer_id == user.id else None
