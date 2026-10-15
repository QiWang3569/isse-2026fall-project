"""Shared item visibility and conversation transitions for seller and chat actions."""
from fastapi import HTTPException
from sqlalchemy import select, update

from .models import ChatMessage, Conversation, SaleFeedback


PUBLIC_ITEM_STATES = ('ACTIVE', 'RESERVED', 'SOLD', 'EXPIRED')
OPEN_DEAL_STATES = ('REQUESTED', 'RESERVED', 'SOLD')


def can_manage(item, user):
    return bool(user and (user.id == item.seller_id or user.role == 'admin'))


def deal_states(db, item):
    return set(db.scalars(select(Conversation.deal_status).where(Conversation.item_id == item.id)))


def item_capabilities(db, item, user):
    owned = bool(user and user.id == item.seller_id)
    states = deal_states(db, item) if owned else set()
    return {
        'can_relist': owned and item.status in {'RESERVED', 'EXPIRED', 'SOLD'}
            and not states.intersection({'SOLD', 'CONFIRMED'}),
        'can_withdraw': owned and item.status in {'ACTIVE', 'EXPIRED', 'SOLD'}
            and not states.intersection(OPEN_DEAL_STATES),
        'can_duplicate': owned and item.status == 'SOLD' and 'CONFIRMED' in states
            and not states.intersection(OPEN_DEAL_STATES),
    }


def change_conversation(db, conversation, status, actor_id, body):
    if conversation.deal_status == status:
        return
    conversation.deal_status = status
    message = ChatMessage(conversation_id=conversation.id, sender_id=actor_id, body=body)
    db.add(message)
    db.flush()
    conversation.last_message_at = message.created_at


def sync_conversations(db, item, target, actor_id, exclude_id=None):
    """Apply the same side effects regardless of the entry point that changed an item."""
    rows = db.scalars(select(Conversation).where(Conversation.item_id == item.id,
                      Conversation.deal_status.in_(['REQUESTED', 'RESERVED']))).all()
    for conversation in rows:
        if conversation.id == exclude_id:
            continue
        state = conversation.deal_status
        if target == 'SOLD':
            status = 'SOLD' if state == 'RESERVED' else 'DECLINED'
            body = '我已标记商品售出，请确认收货' if state == 'RESERVED' else '商品已售出，本次预订申请已结束'
        elif target in {'BANNED', 'WITHDRAWN', 'EXPIRED'}:
            status = 'CANCELED' if state == 'RESERVED' else 'DECLINED'
            body = '商品已停止出售，本次预订已结束'
        elif target == 'ACTIVE' and state == 'RESERVED':
            status, body = 'CANCELED', '卖家已取消预订，商品恢复在售'
        else:
            continue
        change_conversation(db, conversation, status, actor_id, body)
    if target == 'SOLD':
        db.execute(update(SaleFeedback).where(SaleFeedback.item_id == item.id,
                   SaleFeedback.status == 'OPEN').values(status='CONFIRMED'))


def validate_seller_status(db, item, target):
    if item.status not in PUBLIC_ITEM_STATES:
        raise HTTPException(409, '审核隐藏或已撤回的商品不能修改售卖状态')
    if target == item.status:
        return
    states = deal_states(db, item)
    if target in {'ACTIVE', 'RESERVED'} and states.intersection({'SOLD', 'CONFIRMED'}):
        raise HTTPException(409, '请保留原成交记录；确认收货后可使用“再发一件”')
    if target == 'RESERVED' and 'REQUESTED' in states:
        raise HTTPException(409, '已有买家申请预订，请先在站内消息中确认或拒绝')
    if target == 'RESERVED' and item.status != 'ACTIVE':
        raise HTTPException(409, '请先重新上架，再确认预订')
    if target == 'SOLD' and item.status not in {'ACTIVE', 'RESERVED'}:
        raise HTTPException(409, '请先重新上架再标记售出')
