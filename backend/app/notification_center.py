"""Counts are independent of list limits; reading is separate from resolving a task."""
from fastapi import Depends, HTTPException, Query
from sqlalchemy import func, or_, select

from .models import (Announcement, AnnouncementRead, ChatMessage, Conversation,
                     FeedbackNotice, Item, Notification, SaleFeedback, now)


def register_notification_center(app, get_db, current_user, require_user, mutation_lock):
    def announcement_conditions(user, unread_only):
        conditions = [Announcement.active == True]
        if unread_only:
            if not user:
                raise HTTPException(401, '请先登录')
            read = select(AnnouncementRead.announcement_id).where(AnnouncementRead.user_id == user.id)
            conditions.append(Announcement.id.not_in(read))
        return conditions

    @app.get('/api/v1/announcements/feed')
    def announcements(page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=50),
                      unread_only: bool = False, db=Depends(get_db), user=Depends(current_user)):
        conditions = announcement_conditions(user, unread_only)
        rows = db.scalars(select(Announcement).where(*conditions).order_by(
            Announcement.created_at.desc(), Announcement.id.desc()).offset((page - 1) * size).limit(size)).all()
        read = set(db.scalars(select(AnnouncementRead.announcement_id).where(
            AnnouncementRead.user_id == user.id, AnnouncementRead.announcement_id.in_([a.id for a in rows])))) if user else set()
        return {'items': [{'id': a.id, 'title': a.title, 'body': a.body, 'kind': a.kind,
                           'created_at': a.created_at.isoformat() + 'Z',
                           'is_read': a.id in read if user else None} for a in rows],
                'total': db.scalar(select(func.count()).select_from(Announcement).where(*conditions)),
                'page': page, 'size': size}

    @app.get('/api/v1/notification-summary')
    def summary(db=Depends(get_db), user=Depends(require_user)):
        def count(model, *conditions):
            return db.scalar(select(func.count()).select_from(model).where(*conditions)) or 0

        chats = select(Conversation.id).where(or_(Conversation.buyer_id == user.id, Conversation.seller_id == user.id))
        own_items = select(Item.id).where(Item.seller_id == user.id)
        counts = {
            'announcements': count(Announcement, *announcement_conditions(user, True)),
            'chat': count(ChatMessage, ChatMessage.conversation_id.in_(chats),
                          ChatMessage.sender_id != user.id, ChatMessage.read_at.is_(None)),
            'matches': count(Notification, Notification.buyer_id == user.id,
                             Notification.verdict != 'NO_MATCH', Notification.is_read == False),
            'feedback': count(FeedbackNotice, FeedbackNotice.user_id == user.id, FeedbackNotice.is_read == False),
            'sale_feedback': count(SaleFeedback, SaleFeedback.item_id.in_(own_items),
                                   SaleFeedback.status == 'OPEN', SaleFeedback.read_at.is_(None)),
        }
        return {**counts, 'total': sum(counts.values()), 'pending_sale_feedback': count(
            SaleFeedback, SaleFeedback.item_id.in_(own_items), SaleFeedback.status == 'OPEN')}

    @app.post('/api/v1/sale-feedback/{feedback_id}/read')
    def read_sale_feedback(feedback_id: str, db=Depends(get_db), user=Depends(require_user)):
        with mutation_lock:
            row = db.scalar(select(SaleFeedback).join(Item, Item.id == SaleFeedback.item_id).where(
                SaleFeedback.id == feedback_id, Item.seller_id == user.id).with_for_update())
            if not row:
                raise HTTPException(404, '反馈不存在')
            if row.read_at is None:
                row.read_at = now()
                db.commit()
        return {'ok': True}
