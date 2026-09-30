import hashlib
import hmac
import io
import logging
import secrets
import smtplib
import threading
import warnings
from contextlib import asynccontextmanager
from datetime import timedelta
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, Query, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, UnidentifiedImageError
from sqlalchemy import create_engine, event, func, or_, select, text, update
from sqlalchemy.orm import Session, sessionmaker

from .config import ROOT, Settings
from .email_auth import code_digest, new_code, normalize_pku_email, send_verification_email
from .matching import MatchingRunner
from .migrations import upgrade_buyer_agent
from .models import ActionLog, Base, ChatMessage, Conversation, EmailChallenge, Favorite, Intent, Item, LoginSession, MatchJob, Notification, Report, Upload, User, Wanted, now, uid
from .schemas import CAMPUSES, CATEGORIES, CONDITIONS, ChatMessageCreate, DemoLogin, EmailCodeRequest, EmailCodeVerify, IntentChange, IntentCreate, ItemCreate, QueryIn, ReportCreate, ReviewAction, StatusChange, WantedCreate
from .services import FEATURES, assess_report, embed, log, model_name, normalize, parse_intent, seed


def iso(value):
    return value.isoformat() + 'Z'


def create_app(settings: Settings | None = None):
    settings = settings or Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    upload_dir = settings.data_dir / 'uploads'
    upload_dir.mkdir(exist_ok=True)
    engine = create_engine(settings.database_url, connect_args={'check_same_thread': False, 'timeout': 30} if settings.database_url.startswith('sqlite') else {}, pool_pre_ping=True)
    if engine.dialect.name == 'sqlite':
        @event.listens_for(engine, 'connect')
        def sqlite_setup(connection, _):
            connection.execute('PRAGMA foreign_keys=ON')
            connection.execute('PRAGMA journal_mode=WAL')
    factory = sessionmaker(engine, expire_on_commit=False)
    mutation_lock = threading.RLock()
    matching = MatchingRunner(factory, settings, mutation_lock)

    @asynccontextmanager
    async def lifespan(app):
        if engine.dialect.name == 'postgresql':
            with engine.begin() as conn:
                conn.execute(text('CREATE EXTENSION IF NOT EXISTS vector'))
        Base.metadata.create_all(engine)
        upgrade_buyer_agent(engine)
        if engine.dialect.name == 'postgresql':
            with engine.begin() as conn:
                conn.execute(text('CREATE INDEX IF NOT EXISTS idx_items_embedding_hnsw ON items USING hnsw (embedding vector_cosine_ops)'))
        if settings.demo_mode:
            with factory() as db:
                seed(db)
        matching.start()
        try:
            yield
        finally:
            matching.stop()
            engine.dispose()

    app = FastAPI(title='燕渡 API', version='0.1.0', lifespan=lifespan)
    app.state.engine = engine
    app.state.session_factory = factory
    app.state.settings = settings
    app.state.matching = matching
    app.state.mutation_lock = mutation_lock
    app.add_middleware(CORSMiddleware, allow_origins=settings.origins, allow_credentials=True, allow_methods=['GET', 'POST', 'PATCH', 'DELETE'], allow_headers=['Content-Type'])

    @app.middleware('http')
    async def mutation_origin_guard(request: Request, call_next):
        origin = request.headers.get('origin')
        if request.method not in {'GET', 'HEAD', 'OPTIONS'} and origin and origin not in settings.origins:
            return JSONResponse({'detail': '请求来源不受信任'}, status_code=403)
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        if request.url.path.startswith('/api/'):
            response.headers['Cache-Control'] = 'no-store'
        return response

    def get_db():
        with factory() as db:
            instant = now()
            for cls in (Item, Intent, Wanted):
                db.execute(update(cls).where(cls.expires_at <= instant, cls.status.in_(['ACTIVE', 'PAUSED', 'RESERVED'])).values(status='EXPIRED'))
            db.commit()
            yield db

    def current_user(request: Request, db: Session = Depends(get_db)):
        token = request.cookies.get('yandu_session', '')
        session = db.get(LoginSession, hashlib.sha256(token.encode()).hexdigest()) if token else None
        return db.get(User, session.user_id) if session and session.expires_at > now() else None

    def require_user(user: User | None = Depends(current_user)):
        if not user:
            raise HTTPException(401, '请先登录后再操作')
        return user

    def require_admin(user: User = Depends(require_user)):
        if user.role != 'admin':
            raise HTTPException(403, '仅管理员可执行此操作')
        return user

    def get_item(db, item_id):
        item = db.get(Item, item_id)
        if not item:
            raise HTTPException(404, '商品不存在')
        return item

    def user_out(user):
        return {'id': user.id, 'nickname': user.nickname, 'campus': user.campus, 'role': user.role} if user else None

    def own_user_out(user):
        return {**user_out(user), 'email': user.email} if user else None

    def begin_session(request, response, db, user):
        old = request.cookies.get('yandu_session', '')
        if old and (old_session := db.get(LoginSession, hashlib.sha256(old.encode()).hexdigest())):
            db.delete(old_session)
        token = secrets.token_urlsafe(32)
        db.add(LoginSession(token_hash=hashlib.sha256(token.encode()).hexdigest(), user_id=user.id, expires_at=now()+timedelta(days=1)))
        db.commit()
        response.set_cookie('yandu_session', token, httponly=True, samesite='strict', secure=request.url.scheme == 'https', max_age=86400)
        return {'user': own_user_out(user)}

    def item_out(item, db, user=None):
        seller = db.get(User, item.seller_id)
        return {'id': item.id, 'title': item.title, 'description': item.description, 'category': item.category,
                'price': item.price_cents / 100, 'campus': item.campus, 'condition_grade': item.condition_grade,
                'tags': item.tags, 'images': item.images, 'art': item.art, 'status': item.status,
                'seller': user_out(seller), 'created_at': iso(item.created_at), 'expires_at': iso(item.expires_at),
                'is_favorite': bool(user and db.get(Favorite, (user.id, item.id))),
                'is_owner': bool(user and user.id == item.seller_id), 'is_demo': item.id.startswith('sample-')}

    def intent_out(intent, db):
        count = db.scalar(select(func.count()).select_from(Notification).where(Notification.intent_id == intent.id, Notification.verdict != 'NO_MATCH'))
        job = db.scalar(select(MatchJob).where(MatchJob.target_id == intent.id).order_by(MatchJob.created_at.desc()).limit(1))
        outstanding = db.scalar(select(MatchJob).where(MatchJob.target_id == intent.id, MatchJob.status.in_(['PENDING', 'RUNNING', 'FAILED'])).order_by(MatchJob.created_at.desc()).limit(1))
        state = (outstanding or job).status if outstanding or job else 'DONE'
        return {'id': intent.id, 'raw_query': intent.raw_query, 'category': intent.category,
                'max_price': intent.max_price_cents / 100 if intent.max_price_cents is not None else None,
                'campus': intent.campus, 'keywords': intent.keywords, 'condition_grade': intent.condition_grade,
                'excluded_keywords': intent.excluded_keywords, 'preferences': intent.preferences, 'clarification': None,
                'matching_state': state,
                'status': intent.status, 'match_count': count, 'created_at': iso(intent.created_at),
                'expires_at': iso(intent.expires_at), 'matching_mode': intent.embedding_model}

    def owned_intent(db, id, user):
        intent = db.get(Intent, id)
        if not intent or intent.buyer_id != user.id:
            raise HTTPException(404, '代蹲任务不存在')
        return intent

    def check_intent_limit(db, user, exclude=None):
        # PostgreSQL row lock and in-process lock protect the per-user quota.
        db.scalar(select(User).where(User.id == user.id).with_for_update())
        query = select(func.count()).select_from(Intent).where(Intent.buyer_id == user.id, Intent.status == 'ACTIVE', Intent.expires_at > now())
        if exclude:
            query = query.where(Intent.id != exclude)
        if db.scalar(query) >= 5:
            raise HTTPException(409, '最多同时运行 5 个代蹲任务，请先暂停或结束一个任务')

    @app.get('/api/v1/health')
    def health():
        return {'status': 'ok', 'version': '0.1.0', 'demo_mode': settings.demo_mode, 'ai_mode': settings.ai_mode}

    @app.get('/api/v1/meta')
    def meta(db: Session = Depends(get_db)):
        return {'categories': CATEGORIES, 'campuses': CAMPUSES, 'conditions': CONDITIONS,
                'demo_mode': settings.demo_mode, 'ai_mode': settings.ai_mode, 'embedding_mode': settings.embedding_mode,
                'email_auth_ready': settings.email_auth_ready,
                'active_items': db.scalar(select(func.count()).select_from(Item).where(Item.status == 'ACTIVE', Item.expires_at > now()))}

    @app.get('/api/v1/auth/me')
    def me(user=Depends(current_user)):
        return {'user': own_user_out(user)}

    @app.post('/api/v1/auth/email/request-code')
    def request_email_code(data: EmailCodeRequest, db: Session = Depends(get_db)):
        email = normalize_pku_email(data.email)
        if not email:
            raise HTTPException(422, '仅支持 @pku.edu.cn 或 @stu.pku.edu.cn 邮箱')
        if not settings.email_auth_ready:
            raise HTTPException(503, '邮件登录尚未配置，请联系管理员')
        with mutation_lock:
            instant = now()
            challenge = db.get(EmailChallenge, email)
            if challenge and (instant - challenge.sent_at).total_seconds() < 60:
                raise HTTPException(429, '请一分钟后再获取验证码')
            if challenge and (instant - challenge.window_started_at).total_seconds() < 3600 and challenge.sends_in_window >= 5:
                raise HTTPException(429, '验证码请求过于频繁，请稍后再试')
            code = new_code()
            challenge_id = uid()
            try:
                send_verification_email(settings, email, code)
            except (OSError, smtplib.SMTPException) as exc:
                logging.getLogger(__name__).warning('SMTP delivery failed: %s (code %s)',
                                                    type(exc).__name__, getattr(exc, 'smtp_code', None))
                raise HTTPException(502, '邮件发送失败，请稍后再试') from None
            if challenge:
                if (instant - challenge.window_started_at).total_seconds() >= 3600:
                    challenge.window_started_at, challenge.sends_in_window = instant, 0
                challenge.sends_in_window += 1
                challenge.challenge_id = challenge_id
                challenge.code_hash = code_digest(settings.auth_secret, challenge_id, email, code)
                challenge.expires_at = instant + timedelta(minutes=10)
                challenge.sent_at, challenge.attempts = instant, 0
            else:
                db.add(EmailChallenge(email=email, challenge_id=challenge_id,
                                      code_hash=code_digest(settings.auth_secret, challenge_id, email, code),
                                      expires_at=instant+timedelta(minutes=10), sent_at=instant,
                                      window_started_at=instant, sends_in_window=1, attempts=0))
            db.commit()
        return {'ok': True, 'message': '验证码已发送，请检查邮箱'}

    @app.post('/api/v1/auth/email/verify')
    def verify_email_code(data: EmailCodeVerify, request: Request, response: Response, db: Session = Depends(get_db)):
        email = normalize_pku_email(data.email)
        if not email:
            raise HTTPException(422, '仅支持 @pku.edu.cn 或 @stu.pku.edu.cn 邮箱')
        if not settings.email_auth_ready:
            raise HTTPException(503, '邮件登录尚未配置，请联系管理员')
        with mutation_lock:
            challenge = db.get(EmailChallenge, email)
            if not challenge or challenge.expires_at <= now() or challenge.attempts >= 5:
                raise HTTPException(400, '验证码无效或已过期，请重新获取')
            expected = code_digest(settings.auth_secret, challenge.challenge_id, email, data.code)
            if not hmac.compare_digest(challenge.code_hash, expected):
                challenge.attempts += 1
                db.commit()
                raise HTTPException(400, '验证码无效或已过期，请重新获取')
            user = db.scalar(select(User).where(User.email == email))
            if not user:
                nickname = data.nickname.strip()
                if len(nickname) < 2:
                    raise HTTPException(422, '首次注册请填写至少两个字的昵称')
                user = User(email=email, nickname=nickname, campus=data.campus, role='student')
                db.add(user)
                db.flush()
            db.delete(challenge)
            return begin_session(request, response, db, user)

    @app.post('/api/v1/auth/demo')
    def login(data: DemoLogin, request: Request, response: Response, db: Session = Depends(get_db)):
        if not settings.demo_mode:
            raise HTTPException(503, '演示登录已关闭，请使用北大邮箱登录')
        user = db.get(User, 'demo-' + data.profile)
        return begin_session(request, response, db, user)

    @app.post('/api/v1/auth/logout')
    def logout(request: Request, response: Response, db: Session = Depends(get_db)):
        token = request.cookies.get('yandu_session', '')
        row = db.get(LoginSession, hashlib.sha256(token.encode()).hexdigest())
        if row:
            db.delete(row)
            db.commit()
        response.delete_cookie('yandu_session')
        return {'ok': True}

    def owned_conversation(db, conversation_id, user):
        conversation = db.get(Conversation, conversation_id)
        if not conversation or user.id not in {conversation.buyer_id, conversation.seller_id}:
            raise HTTPException(404, '会话不存在')
        return conversation

    def message_out(message):
        return {'id': message.id, 'conversation_id': message.conversation_id,
                'sender_id': message.sender_id, 'body': message.body,
                'created_at': iso(message.created_at),
                'read_at': iso(message.read_at) if message.read_at else None}

    def conversation_out(db, conversation, user):
        item = db.get(Item, conversation.item_id)
        counterpart_id = conversation.seller_id if user.id == conversation.buyer_id else conversation.buyer_id
        last_message = db.scalar(select(ChatMessage).where(ChatMessage.conversation_id == conversation.id)
                                 .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc()).limit(1))
        unread = db.scalar(select(func.count()).select_from(ChatMessage).where(
            ChatMessage.conversation_id == conversation.id, ChatMessage.sender_id != user.id,
            ChatMessage.read_at.is_(None)))
        return {'id': conversation.id, 'item_id': item.id, 'item_title': item.title,
                'item_status': item.status, 'item_image': item.images[0] if item.images else None,
                'counterpart': user_out(db.get(User, counterpart_id)),
                'last_message': message_out(last_message) if last_message else None,
                'unread_count': unread, 'updated_at': iso(conversation.last_message_at)}

    @app.get('/api/v1/conversations')
    def conversations(db: Session = Depends(get_db), user=Depends(require_user)):
        rows = db.scalars(select(Conversation).where(or_(Conversation.buyer_id == user.id, Conversation.seller_id == user.id))
                          .order_by(Conversation.last_message_at.desc()).limit(100)).all()
        return [conversation_out(db, row, user) for row in rows]

    @app.post('/api/v1/items/{item_id}/conversations', status_code=201)
    def start_conversation(item_id: str, data: ChatMessageCreate, db: Session = Depends(get_db), user=Depends(require_user)):
        with mutation_lock:
            item = get_item(db, item_id)
            if item.seller_id == user.id:
                raise HTTPException(403, '不能给自己的商品发消息')
            if item.status != 'ACTIVE' or item.expires_at <= now():
                raise HTTPException(409, '商品当前不可咨询')
            conversation = db.scalar(select(Conversation).where(Conversation.item_id == item.id,
                                    Conversation.buyer_id == user.id))
            if not conversation:
                conversation = Conversation(item_id=item.id, buyer_id=user.id, seller_id=item.seller_id)
                db.add(conversation)
                db.flush()
            message = ChatMessage(conversation_id=conversation.id, sender_id=user.id, body=data.body)
            db.add(message)
            db.flush()
            conversation.last_message_at = message.created_at
            db.commit()
            return {'conversation': conversation_out(db, conversation, user), 'message': message_out(message)}

    @app.get('/api/v1/conversations/{conversation_id}/messages')
    def conversation_messages(conversation_id: str, before_id: str | None = None,
                              db: Session = Depends(get_db), user=Depends(require_user)):
        owned_conversation(db, conversation_id, user)
        query = select(ChatMessage).where(ChatMessage.conversation_id == conversation_id)
        if before_id:
            anchor = db.get(ChatMessage, before_id)
            if not anchor or anchor.conversation_id != conversation_id:
                raise HTTPException(404, '消息不存在')
            query = query.where(or_(ChatMessage.created_at < anchor.created_at,
                                    (ChatMessage.created_at == anchor.created_at) & (ChatMessage.id < anchor.id)))
        rows = db.scalars(query.order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc()).limit(51)).all()
        return {'messages': [message_out(row) for row in reversed(rows[:50])], 'has_more': len(rows) > 50}

    @app.post('/api/v1/conversations/{conversation_id}/messages', status_code=201)
    def send_message(conversation_id: str, data: ChatMessageCreate,
                     db: Session = Depends(get_db), user=Depends(require_user)):
        with mutation_lock:
            conversation = owned_conversation(db, conversation_id, user)
            message = ChatMessage(conversation_id=conversation.id, sender_id=user.id, body=data.body)
            db.add(message)
            db.flush()
            conversation.last_message_at = message.created_at
            db.commit()
            return message_out(message)

    @app.post('/api/v1/conversations/{conversation_id}/read')
    def read_conversation(conversation_id: str, db: Session = Depends(get_db), user=Depends(require_user)):
        owned_conversation(db, conversation_id, user)
        db.execute(update(ChatMessage).where(ChatMessage.conversation_id == conversation_id,
                   ChatMessage.sender_id != user.id, ChatMessage.read_at.is_(None)).values(read_at=now()))
        db.commit()
        return {'ok': True}

    @app.get('/api/v1/items/')
    def items(q: str = Query('', max_length=120), category: str | None = None, campus: str | None = None,
              min_price: float | None = Query(None, ge=0), max_price: float | None = Query(None, ge=0),
              condition_grade: str | None = None, sort: str = 'recommended', mine: bool = False, favorites: bool = False,
              page: int = Query(1, ge=1), size: int = Query(12, ge=1, le=50), db: Session = Depends(get_db), user=Depends(current_user)):
        query = select(Item)
        if mine or favorites:
            if not user:
                raise HTTPException(401, '请先登录')
            if mine:
                query = query.where(Item.seller_id == user.id)
            if favorites:
                query = query.join(Favorite, Favorite.item_id == Item.id).where(Favorite.user_id == user.id)
        else:
            query = query.where(Item.status == 'ACTIVE', Item.expires_at > now())
        if category:
            query = query.where(Item.category == category)
        if campus and campus != '不限校区':
            query = query.where(Item.campus.in_([campus, '不限校区']))
        if min_price is not None:
            query = query.where(Item.price_cents >= round(min_price * 100))
        if max_price is not None:
            query = query.where(Item.price_cents <= round(max_price * 100))
        if condition_grade:
            query = query.where(Item.condition_grade == condition_grade)
        if q.strip():
            for word in q.strip().split():
                aliases = [word, normalize(word)]
                aliases.extend(FEATURES.get(normalize(word), []))
                query = query.where(or_(*(column.contains(w, autoescape=True) for column in [Item.title, Item.description] for w in aliases)))
        total = db.scalar(select(func.count()).select_from(query.subquery()))
        if sort == 'price_asc':
            query = query.order_by(Item.price_cents, Item.created_at.desc())
        elif sort == 'price_desc':
            query = query.order_by(Item.price_cents.desc(), Item.created_at.desc())
        elif sort == 'recommended' and user:
            preferred = select(Item.category).join(Favorite).where(Favorite.user_id == user.id)
            categories = list(db.scalars(preferred))
            query = query.order_by(Item.category.in_(categories).desc(), (Item.campus == user.campus).desc(), Item.created_at.desc())
        else:
            query = query.order_by(Item.created_at.desc())
        return {'items': [item_out(i, db, user) for i in db.scalars(query.offset((page-1)*size).limit(size))], 'total': total, 'page': page, 'size': size}

    @app.get('/api/v1/items/{item_id}')
    def item_detail(item_id: str, db: Session = Depends(get_db), user=Depends(current_user)):
        return item_out(get_item(db, item_id), db, user)

    @app.post('/api/v1/uploads', status_code=201)
    def upload(file: UploadFile = File(...), user=Depends(require_user), db: Session = Depends(get_db)):
        raw = file.file.read(6*1024*1024+1)
        if len(raw) > 6*1024*1024:
            raise HTTPException(413, '每张图片不得超过 6 MB')
        try:
            with warnings.catch_warnings():
                warnings.simplefilter('error', Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(raw)) as im:
                    if im.format not in {'PNG', 'JPEG', 'WEBP'}:
                        raise ValueError('format')
                    if im.width * im.height > 20_000_000:
                        raise ValueError('dimensions')
                    im.load()
                    im = im.convert('RGB')
                    im.thumbnail((1600, 1600))
                    name = uid() + '.jpg'
                    im.save(upload_dir / name, 'JPEG', quality=88)
        except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
            raise HTTPException(422, '请上传有效的 JPG、PNG 或 WebP 图片（不超过 2000 万像素）')
        path = '/uploads/' + name
        db.add(Upload(path=path, user_id=user.id))
        db.commit()
        return {'url': path}

    @app.post('/api/v1/items/', status_code=201)
    def publish(data: ItemCreate, db: Session = Depends(get_db), user=Depends(require_user)):
        if not data.images:
            raise HTTPException(422, '请至少上传一张商品照片')
        for path in data.images:
            image = db.get(Upload, path)
            if not image or image.user_id != user.id:
                raise HTTPException(422, '只能使用自己上传的商品图片')
        values = data.model_dump(exclude={'price'})
        db.commit()  # Release the read transaction before contacting a provider.
        vector = embed(data.title + ' ' + data.description + ' ' + ' '.join(data.tags), settings)
        item = Item(**values, seller_id=user.id, price_cents=int(data.price*100), embedding=vector, embedding_model=model_name(settings))
        with mutation_lock:
            db.add(item)
            db.flush()
            jobs = matching.enqueue_item(db, item)
            log(db, user, 'item.publish', item.id)
            db.commit()
        for job_id in jobs:
            matching.run_or_wake(job_id)
        return item_out(item, db, user)

    @app.patch('/api/v1/items/{item_id}/status')
    def item_status(item_id: str, data: StatusChange, db: Session = Depends(get_db), user=Depends(require_user)):
        with mutation_lock:
            item = db.scalar(select(Item).where(Item.id == item_id).with_for_update().execution_options(populate_existing=True))
            if not item:
                raise HTTPException(404, '商品不存在')
            if item.seller_id != user.id:
                raise HTTPException(403, '只能修改自己发布的商品')
            if item.status in {'BANNED', 'SOLD'}:
                raise HTTPException(409, '已售出或审核隐藏的商品不能由卖家重新上架')
            item.status = data.status
            if data.status == 'ACTIVE':
                item.expires_at = now()+timedelta(days=14)
            db.flush()
            jobs = matching.enqueue_item(db, item) if data.status == 'ACTIVE' else []
            log(db, user, 'item.status', item.id, data.status)
            db.commit()
        for job_id in jobs:
            matching.run_or_wake(job_id)
        return item_out(item, db, user)

    @app.post('/api/v1/items/{item_id}/favorite')
    def favorite(item_id: str, db: Session = Depends(get_db), user=Depends(require_user)):
        item = get_item(db, item_id)
        if not db.get(Favorite, (user.id, item_id)):
            db.add(Favorite(user_id=user.id, item_id=item_id))
            db.commit()
        return item_out(item, db, user)

    @app.delete('/api/v1/items/{item_id}/favorite')
    def unfavorite(item_id: str, db: Session = Depends(get_db), user=Depends(require_user)):
        if fav := db.get(Favorite, (user.id, item_id)):
            db.delete(fav)
            db.commit()
        return {'ok': True}

    @app.post('/api/v1/items/{item_id}/message-draft')
    def message_draft(item_id: str, db: Session = Depends(get_db), user=Depends(require_user)):
        item = get_item(db, item_id)
        if item.status != 'ACTIVE' or item.expires_at <= now():
            raise HTTPException(409, '该商品当前不在售，请查看其他商品')
        notice = db.scalar(select(Notification).where(Notification.item_id == item.id, Notification.buyer_id == user.id).order_by(Notification.created_at.desc()).limit(1))
        questions = notice.questions if notice else []
        extra = ('另外想确认：' + '；'.join(questions)) if questions else ''
        log(db, user, 'message.draft', item.id)
        db.commit()
        return {'draft': f'你好，请问「{item.title}」还在吗？我在{user.campus}，希望确认一下商品状况和方便的当面交易时间。{extra}谢谢！', 'sent': False}

    @app.post('/api/v1/intents/parse')
    def parse(data: QueryIn, db: Session = Depends(get_db), user=Depends(require_user)):
        db.commit()
        return {'parsed': parse_intent(data.raw_query, settings), 'mode': settings.ai_mode}

    @app.post('/api/v1/intents/', status_code=201)
    def add_intent(data: IntentCreate, db: Session = Depends(get_db), user=Depends(require_user)):
        if not data.parsed.keywords:
            raise HTTPException(422, '请至少填写一个具体的物品关键词')
        db.commit()
        vector = embed(' '.join(data.parsed.keywords), settings)
        parsed = data.parsed
        intent = Intent(buyer_id=user.id, raw_query=data.raw_query, category=parsed.category,
                        max_price_cents=int(parsed.max_price*100) if parsed.max_price is not None else None,
                        campus=parsed.campus, keywords=parsed.keywords, condition_grade=parsed.condition_grade,
                        excluded_keywords=parsed.excluded_keywords, preferences=parsed.preferences,
                        embedding=vector, embedding_model=model_name(settings))
        with mutation_lock:
            check_intent_limit(db, user)
            db.add(intent)
            db.flush()
            job_id = matching.enqueue(db, 'intent', intent.id)
            log(db, user, 'intent.create', intent.id)
            db.commit()
        matching.run_or_wake(job_id)
        matches = db.scalars(select(Item).join(Notification, Notification.item_id == Item.id).where(Notification.intent_id == intent.id, Notification.verdict != 'NO_MATCH')).all()
        return {'intent': intent_out(intent, db), 'matches': [item_out(i, db, user) for i in matches]}

    @app.get('/api/v1/intents/my')
    def my_intents(db: Session = Depends(get_db), user=Depends(require_user)):
        return [intent_out(i, db) for i in db.scalars(select(Intent).where(Intent.buyer_id == user.id).order_by(Intent.created_at.desc()))]

    @app.patch('/api/v1/intents/{intent_id}')
    def change_intent(intent_id: str, data: IntentChange, db: Session = Depends(get_db), user=Depends(require_user)):
        with mutation_lock:
            intent = owned_intent(db, intent_id, user)
            if intent.status == 'COMPLETED':
                raise HTTPException(409, '已结束的任务不能恢复，请新建任务')
            if data.action == 'pause':
                intent.status = 'PAUSED'
            else:
                check_intent_limit(db, user, intent.id)
                if data.action == 'renew':
                    intent.expires_at = now()+timedelta(days=14)
                elif intent.expires_at <= now():
                    raise HTTPException(409, '任务已过期，请先续期')
                intent.status = 'ACTIVE'
                job_id = matching.enqueue(db, 'intent', intent.id)
            log(db, user, 'intent.'+data.action, intent.id)
            db.commit()
        if data.action != 'pause':
            matching.run_or_wake(job_id)
        return intent_out(intent, db)

    @app.post('/api/v1/intents/{intent_id}/retry')
    def retry_matching(intent_id: str, db: Session = Depends(get_db), user=Depends(require_user)):
        with mutation_lock:
            intent = owned_intent(db, intent_id, user)
            if intent.status != 'ACTIVE' or intent.expires_at <= now():
                raise HTTPException(409, '请先恢复或续期代蹲任务')
            failed = db.scalars(select(MatchJob).where(MatchJob.target_id == intent_id, MatchJob.status == 'FAILED')).all()
            if not failed:
                raise HTTPException(409, '没有需要重试的失败匹配任务')
            for job in failed:
                job.status, job.attempts, job.error_code, job.available_at = 'PENDING', 0, '', now()
            job_ids = [j.id for j in failed]
            log(db, user, 'intent.retry', intent_id)
            db.commit()
        for job_id in job_ids:
            matching.run_or_wake(job_id)
        return intent_out(intent, db)

    @app.delete('/api/v1/intents/{intent_id}')
    def end_intent(intent_id: str, db: Session = Depends(get_db), user=Depends(require_user)):
        with mutation_lock:
            intent = owned_intent(db, intent_id, user)
            intent.status = 'COMPLETED'
            log(db, user, 'intent.complete', intent.id)
            db.commit()
        return {'ok': True}

    @app.get('/api/v1/notifications/')
    def notifications(intent_id: str | None = None, db: Session = Depends(get_db), user=Depends(require_user)):
        query = select(Notification).where(Notification.buyer_id == user.id, Notification.verdict != 'NO_MATCH')
        if intent_id is not None:
            owned_intent(db, intent_id, user)
            query = query.where(Notification.intent_id == intent_id)
        rows = db.scalars(query.order_by(Notification.created_at.desc()).limit(100))
        return [{'id': n.id, 'intent_id': n.intent_id, 'item': item_out(db.get(Item, n.item_id), db, user),
                 'score': n.score, 'reason': n.reason, 'verdict': n.verdict, 'questions': n.questions,
                 'evidence': n.evidence, 'review_mode': n.review_mode, 'score_kind': 'embedding_similarity' if db.get(Intent, n.intent_id).embedding_model != 'local-keyword' else 'keyword_coverage', 'is_read': n.is_read, 'created_at': iso(n.created_at),
                 'available': db.get(Item, n.item_id).status == 'ACTIVE' and db.get(Item, n.item_id).expires_at > now()} for n in rows]

    @app.patch('/api/v1/notifications/{notification_id}/read')
    def read_notice(notification_id: str, db: Session = Depends(get_db), user=Depends(require_user)):
        notice = db.get(Notification, notification_id)
        if not notice or notice.buyer_id != user.id:
            raise HTTPException(404, '通知不存在')
        notice.is_read = True
        db.commit()
        return {'ok': True}

    @app.get('/api/v1/wanted/')
    def wanted_list(db: Session = Depends(get_db), user=Depends(current_user)):
        rows = db.scalars(select(Wanted).where(Wanted.status == 'ACTIVE', Wanted.expires_at > now()).order_by(Wanted.created_at.desc()).limit(100))
        return [{'id': w.id, 'title': w.title, 'description': w.description, 'category': w.category,
                 'budget': w.budget_cents/100, 'campus': w.campus, 'buyer': user_out(db.get(User, w.buyer_id)),
                 'is_owner': bool(user and w.buyer_id == user.id), 'created_at': iso(w.created_at), 'expires_at': iso(w.expires_at)} for w in rows]

    @app.post('/api/v1/wanted/', status_code=201)
    def wanted_create(data: WantedCreate, db: Session = Depends(get_db), user=Depends(require_user)):
        w = Wanted(**data.model_dump(exclude={'budget'}), buyer_id=user.id, budget_cents=int(data.budget*100))
        db.add(w)
        db.flush()
        log(db, user, 'wanted.create', w.id)
        db.commit()
        return {'id': w.id}

    @app.delete('/api/v1/wanted/{wanted_id}')
    def wanted_close(wanted_id: str, db: Session = Depends(get_db), user=Depends(require_user)):
        w = db.get(Wanted, wanted_id)
        if not w or w.buyer_id != user.id:
            raise HTTPException(404, '求购不存在')
        w.status = 'COMPLETED'
        db.commit()
        return {'ok': True}

    @app.post('/api/v1/items/{item_id}/reports', status_code=201)
    def report_item(item_id: str, data: ReportCreate, db: Session = Depends(get_db), user=Depends(require_user)):
        item = get_item(db, item_id)
        if db.scalar(select(Report).where(Report.item_id == item_id, Report.reporter_id == user.id, Report.status == 'OPEN')):
            raise HTTPException(409, '你已举报该商品，管理员正在处理中')
        risk, evidence = assess_report(db, item, data.reason)
        report = Report(reporter_id=user.id, item_id=item_id, reason=data.reason, risk=risk, evidence=evidence)
        db.add(report)
        db.flush()
        log(db, user, 'report.create', report.id)
        db.commit()
        return {'id': report.id, 'status': report.status}

    @app.get('/api/v1/admin/reports')
    def admin_reports(db: Session = Depends(get_db), user=Depends(require_admin)):
        return [{'id': r.id, 'item': item_out(db.get(Item, r.item_id), db, user), 'reason': r.reason,
                 'risk': r.risk, 'evidence': r.evidence, 'status': r.status, 'created_at': iso(r.created_at)}
                for r in db.scalars(select(Report).order_by(Report.created_at.desc()).limit(100))]

    @app.post('/api/v1/admin/reports/{report_id}/review')
    def review(report_id: str, data: ReviewAction, db: Session = Depends(get_db), user=Depends(require_admin)):
        with mutation_lock:
            report = db.get(Report, report_id)
            if not report:
                raise HTTPException(404, '举报不存在')
            item = db.scalar(select(Item).where(Item.id == report.item_id).with_for_update().execution_options(populate_existing=True))
            if data.action == 'hide':
                if item.status == 'SOLD':
                    raise HTTPException(409, '已售商品不能隐藏后重新上架')
                item.status = 'BANNED'
            elif data.action == 'restore':
                if item.status != 'BANNED':
                    raise HTTPException(409, '仅可恢复审核隐藏的商品')
                item.status = 'ACTIVE' if item.expires_at > now() else 'EXPIRED'
            report.status = {'hide': 'HIDDEN', 'restore': 'RESTORED', 'dismiss': 'DISMISSED'}[data.action]
            log(db, user, 'admin.'+data.action, item.id, data.note)
            db.flush()
            jobs = matching.enqueue_item(db, item) if data.action == 'restore' and item.status == 'ACTIVE' else []
            db.commit()
        for job_id in jobs:
            matching.run_or_wake(job_id)
        return {'ok': True}

    @app.get('/api/v1/admin/logs')
    def admin_logs(db: Session = Depends(get_db), user=Depends(require_admin)):
        return [{'id': l.id, 'action': l.action, 'actor': user_out(db.get(User, l.actor_id)), 'target_id': l.target_id,
                 'detail': l.detail, 'created_at': iso(l.created_at)} for l in db.scalars(select(ActionLog).order_by(ActionLog.created_at.desc()).limit(100))]

    app.mount('/uploads', StaticFiles(directory=upload_dir), name='uploads')
    frontend = ROOT / 'frontend/dist'
    if frontend.exists():
        app.mount('/assets', StaticFiles(directory=frontend / 'assets'), name='assets')

        @app.get('/{path:path}', include_in_schema=False)
        def spa(path: str):
            if path.startswith(('api/', 'uploads/')):
                raise HTTPException(404, '接口不存在')
            return FileResponse(frontend / 'index.html')
    return app


app = create_app()
