"""Private, in-app support conversations. No email delivery is scheduled here."""
import re
from datetime import timedelta
from typing import Literal

from fastapi import Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import Field, field_validator
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from .models import Feedback, FeedbackAttachment, FeedbackNotice, FeedbackReply, User, now
from .schemas import StrictModel
from .services import log

Status = Literal['OPEN', 'IN_PROGRESS', 'RESOLVED', 'DECLINED']
STATUS_TEXT = {'OPEN': '待处理', 'IN_PROGRESS': '处理中', 'RESOLVED': '已解决', 'DECLINED': '暂不采纳'}


class FeedbackCreate(StrictModel):
    category: Literal['功能异常', '使用建议', '其他问题']
    body: str = Field(min_length=5, max_length=3000)
    page_path: str = Field(default='', max_length=500)
    images: list[str] = Field(default_factory=list, max_length=3)

    @field_validator('page_path')
    @classmethod
    def local_path(cls, value):
        if value and (not value.startswith('/') or value.startswith('//') or '\\' in value
                      or '?' in value or any(ord(c) < 32 for c in value)):
            raise ValueError('请仅附带站内页面路径，不包含域名或查询参数')
        return value

    @field_validator('images')
    @classmethod
    def unique_images(cls, value):
        if len(value) != len(set(value)):
            raise ValueError('不能重复添加同一张截图')
        return value


class ReplyCreate(StrictModel):
    body: str = Field(min_length=1, max_length=3000)


class FeedbackReview(StrictModel):
    status: Status
    body: str = Field(min_length=1, max_length=3000)


class FeedbackRead(StrictModel):
    # The detail response provides the IDs actually seen, so a new reply stays unread.
    notice_ids: list[str] = Field(default_factory=list, max_length=100)


def register_feedback(app, get_db, require_user, require_admin, settings, mutation_lock, save_image):
    image_dir = settings.data_dir / 'feedback-uploads'
    image_dir.mkdir(exist_ok=True)

    def iso(value):
        return value.isoformat() + 'Z'

    def owner(db, row):
        user = db.get(User, row.user_id)
        return {'id': user.id, 'nickname': user.nickname}

    def summary(db, row):
        return {'id': row.id, 'category': row.category, 'body': row.body,
                'page_path': row.page_path, 'status': row.status, 'user': owner(db, row),
                'created_at': iso(row.created_at), 'updated_at': iso(row.updated_at)}

    def get_feedback(db, feedback_id, user, staff=False):
        row = db.get(Feedback, feedback_id)
        if not row or (row.user_id != user.id and not (staff and user.role == 'admin')):
            raise HTTPException(404, '反馈不存在或无权查看')
        return row

    def detail(db, row, user):
        replies = db.scalars(select(FeedbackReply).where(FeedbackReply.feedback_id == row.id)
                             .order_by(FeedbackReply.created_at, FeedbackReply.id)).all()
        return {**summary(db, row),
                'images': list(db.scalars(select(FeedbackAttachment.path).where(
                    FeedbackAttachment.feedback_id == row.id).order_by(FeedbackAttachment.created_at)).all()),
                'replies': [{'id': r.id, 'body': r.body, 'is_staff': r.is_staff, 'status': r.status,
                             'author': db.get(User, r.author_id).nickname, 'created_at': iso(r.created_at)} for r in replies],
                'notice_ids': list(db.scalars(select(FeedbackNotice.id).where(
                    FeedbackNotice.feedback_id == row.id, FeedbackNotice.user_id == user.id,
                    FeedbackNotice.is_read == False).limit(100)).all())}

    def rate_limit(db, model, field, user, limit):
        # Serialize each user's submissions on PostgreSQL as well as the single-worker lock.
        db.scalar(select(User).where(User.id == user.id).with_for_update())
        count = db.scalar(select(func.count()).select_from(model).where(
            field == user.id, model.created_at >= now() - timedelta(hours=1)))
        if count >= limit:
            raise HTTPException(429, '提交较频繁，请一小时后再试')

    @app.post('/api/v1/feedback-uploads', status_code=201)
    def upload(file: UploadFile = File(...), db: Session = Depends(get_db), user=Depends(require_user)):
        with mutation_lock:
            rate_limit(db, FeedbackAttachment, FeedbackAttachment.user_id, user, 20)
            result = save_image(file, user, db, purpose='feedback', commit=False)
            db.add(FeedbackAttachment(path=result['url'], user_id=user.id))
            db.commit()
            return result

    @app.get('/api/v1/feedback-images/{name}')
    def image(name: str, db: Session = Depends(get_db), user=Depends(require_user)):
        if not re.fullmatch(r'[0-9a-f-]{36}\.jpg', name):
            raise HTTPException(404, '图片不存在或无权查看')
        attachment = db.get(FeedbackAttachment, '/api/v1/feedback-images/' + name)
        allowed = attachment and (attachment.user_id == user.id or
                                  (attachment.feedback_id is not None and user.role == 'admin'))
        if not allowed or not (image_dir / name).is_file():
            raise HTTPException(404, '图片不存在或无权查看')
        return FileResponse(image_dir / name, media_type='image/jpeg', headers={'Cache-Control': 'private, no-store'})

    @app.post('/api/v1/feedback', status_code=201)
    def create(data: FeedbackCreate, db: Session = Depends(get_db), user=Depends(require_user)):
        with mutation_lock:
            rate_limit(db, Feedback, Feedback.user_id, user, 5)
            images = []
            for path in data.images:
                image = db.scalar(select(FeedbackAttachment).where(FeedbackAttachment.path == path).with_for_update())
                if not image or image.user_id != user.id or image.feedback_id is not None:
                    raise HTTPException(422, '只能添加自己上传且尚未提交的反馈截图')
                images.append(image)
            row = Feedback(user_id=user.id, category=data.category, body=data.body, page_path=data.page_path)
            db.add(row)
            db.flush()
            for image in images:
                image.feedback_id = row.id
            log(db, user, 'feedback.create', row.id)
            db.commit()
            return detail(db, row, user)

    def listing(db, user, page, status=None, staff=False):
        conditions = [] if staff else [Feedback.user_id == user.id]
        if status:
            conditions.append(Feedback.status == status)
        rows = db.scalars(select(Feedback).where(*conditions).order_by(
            Feedback.updated_at.desc(), Feedback.id.desc()).offset((page - 1) * 20).limit(20)).all()
        total = db.scalar(select(func.count()).select_from(Feedback).where(*conditions))
        return {'items': [summary(db, r) for r in rows], 'total': total, 'page': page, 'size': 20}

    @app.get('/api/v1/feedback')
    def mine(page: int = Query(1, ge=1), db: Session = Depends(get_db), user=Depends(require_user)):
        return listing(db, user, page)

    @app.get('/api/v1/feedback-notices')
    def notices(db: Session = Depends(get_db), user=Depends(require_user)):
        query = select(FeedbackNotice).where(FeedbackNotice.user_id == user.id, FeedbackNotice.is_read == False)
        rows = db.scalars(query.order_by(FeedbackNotice.created_at.desc()).limit(50)).all()
        count = db.scalar(select(func.count()).select_from(FeedbackNotice).where(
            FeedbackNotice.user_id == user.id, FeedbackNotice.is_read == False))
        return {'count': count, 'items': [{'id': n.id, 'feedback_id': n.feedback_id, 'body': n.body,
                                         'created_at': iso(n.created_at)} for n in rows]}

    @app.get('/api/v1/feedback/{feedback_id}')
    def view(feedback_id: str, db: Session = Depends(get_db), user=Depends(require_user)):
        with mutation_lock:
            return detail(db, get_feedback(db, feedback_id, user), user)

    @app.post('/api/v1/feedback/{feedback_id}/read')
    def read(feedback_id: str, data: FeedbackRead, db: Session = Depends(get_db), user=Depends(require_user)):
        get_feedback(db, feedback_id, user)
        db.execute(update(FeedbackNotice).where(FeedbackNotice.feedback_id == feedback_id,
                   FeedbackNotice.user_id == user.id, FeedbackNotice.id.in_(data.notice_ids)).values(is_read=True))
        db.commit()
        return {'ok': True}

    @app.post('/api/v1/feedback/{feedback_id}/replies', status_code=201)
    def reply(feedback_id: str, data: ReplyCreate, db: Session = Depends(get_db), user=Depends(require_user)):
        with mutation_lock:
            rate_limit(db, FeedbackReply, FeedbackReply.author_id, user, 30)
            row = get_feedback(db, feedback_id, user)
            # A follow-up on a closed conversation returns it to the work queue.
            status = 'OPEN' if row.status in {'RESOLVED', 'DECLINED'} else None
            if status:
                row.status = status
            row.updated_at = now()
            db.add(FeedbackReply(feedback_id=row.id, author_id=user.id, body=data.body,
                                 status=status, created_at=row.updated_at))
            log(db, user, 'feedback.reply', row.id)
            db.commit()
            return detail(db, row, user)

    @app.get('/api/v1/admin/feedback')
    def admin_list(status: Status | None = None, page: int = Query(1, ge=1),
                   db: Session = Depends(get_db), user=Depends(require_admin)):
        return listing(db, user, page, status, staff=True)

    @app.get('/api/v1/admin/feedback/{feedback_id}')
    def admin_view(feedback_id: str, db: Session = Depends(get_db), user=Depends(require_admin)):
        with mutation_lock:
            return detail(db, get_feedback(db, feedback_id, user, staff=True), user)

    @app.post('/api/v1/admin/feedback/{feedback_id}/reply')
    def admin_reply(feedback_id: str, data: FeedbackReview, db: Session = Depends(get_db), user=Depends(require_admin)):
        with mutation_lock:
            row = get_feedback(db, feedback_id, user, staff=True)
            row.status = data.status
            row.updated_at = now()
            db.add(FeedbackReply(feedback_id=row.id, author_id=user.id, is_staff=True,
                                 body=data.body, status=data.status, created_at=row.updated_at))
            db.add(FeedbackNotice(user_id=row.user_id, feedback_id=row.id, created_at=row.updated_at,
                                  body=f'管理员回复了你的反馈 · {STATUS_TEXT[data.status]}'))
            log(db, user, 'feedback.review', row.id, f'{data.status}: {data.body[:200]}')
            db.commit()
            return detail(db, row, user)
