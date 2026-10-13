from decimal import Decimal
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator

CATEGORIES = ['课程资料与书籍', '数码与影音', '校园出行与运动', '宿舍生活与家电', '美妆服饰与周边', '人员招募']
CAMPUSES = ['燕园校本部', '万柳学区', '医学部', '昌平新校区', '不限校区']
CONDITIONS = ['全新', '95新', '9成新', '8成新', '基本可用']


def valid_duration(value):
    if value not in {0, 7, 14, 30}:
        raise ValueError('有效期请选择 7、14、30 天或长期有效')
    return value


def watch_duration(value):
    if value not in {7, 14, 30}:
        raise ValueError('代蹲有效期请选择 7、14 或 30 天')
    return value


ValidityDays = Annotated[int, Field(strict=True), AfterValidator(valid_duration)]
WatchValidityDays = Annotated[int, Field(strict=True), AfterValidator(watch_duration)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class ExpiryUpdate(StrictModel):
    validity_days: ValidityDays | None = None

    @field_validator('validity_days')
    @classmethod
    def duration_not_null(cls, value):
        if value is None:
            raise ValueError('有效期不能设为空')
        return value


class ItemCreate(StrictModel):
    validity_days: ValidityDays = 14
    title: str = Field(min_length=2, max_length=120)
    description: str = Field(min_length=5, max_length=3000)
    category: str
    price: Decimal = Field(ge=0, le=999999, max_digits=8, decimal_places=2)
    campus: str
    condition_grade: str = '95新'
    tags: list[str] = Field(default_factory=list, max_length=8)
    images: list[str] = Field(default_factory=list, max_length=3)

    @field_validator('category')
    @classmethod
    def category_valid(cls, v):
        if v not in CATEGORIES:
            raise ValueError('请选择有效的商品分类')
        return v

    @field_validator('campus')
    @classmethod
    def campus_valid(cls, v):
        if v not in CAMPUSES:
            raise ValueError('请选择有效的校区')
        return v

    @field_validator('condition_grade')
    @classmethod
    def condition_valid(cls, v):
        if v not in CONDITIONS:
            raise ValueError('请选择有效的成色')
        return v

    @field_validator('tags')
    @classmethod
    def tags_valid(cls, v):
        if any(not t.strip() or len(t) > 30 for t in v):
            raise ValueError('标签长度为 1–30 字')
        return list(dict.fromkeys(t.strip() for t in v))


class QueryIn(StrictModel):
    raw_query: str = Field(min_length=2, max_length=500)


class ParsedIntent(StrictModel):
    category: str | None = None
    max_price: Decimal | None = Field(default=None, ge=0, le=999999, decimal_places=2)
    campus: str = '不限校区'
    keywords: list[str] = Field(default_factory=list, max_length=12)
    excluded_keywords: list[str] = Field(default_factory=list, max_length=12)
    preferences: list[str] = Field(default_factory=list, max_length=12)
    condition_grade: str | None = None
    clarification: str | None = Field(default=None, max_length=500)
    category_valid = field_validator('category')(classmethod(lambda cls, v: ItemCreate.category_valid(v) if v is not None else None))
    campus_valid = field_validator('campus')(classmethod(lambda cls, v: ItemCreate.campus_valid(v)))
    condition_valid = field_validator('condition_grade')(classmethod(lambda cls, v: ItemCreate.condition_valid(v) if v else None))
    tags_valid = field_validator('keywords')(classmethod(lambda cls, v: ItemCreate.tags_valid(v)))
    exclusions_valid = field_validator('excluded_keywords')(classmethod(lambda cls, v: ItemCreate.tags_valid(v)))
    preferences_valid = field_validator('preferences')(classmethod(lambda cls, v: ItemCreate.tags_valid(v)))

    @model_validator(mode='after')
    def consistent_conditions(self):
        if set(self.excluded_keywords) & (set(self.keywords) | set(self.preferences)):
            raise ValueError('同一特征不能同时要求与排除，请调整条件')
        return self


class IntentCreate(QueryIn):
    parsed: ParsedIntent
    validity_days: WatchValidityDays = 14


class SmartSearchIn(StrictModel):
    query: str = Field(min_length=2, max_length=500)
    page: int = Field(default=1, ge=1)
    size: int = Field(default=12, ge=1, le=50)
    sort: Literal['recommended', 'newest', 'price_asc', 'price_desc'] = 'recommended'


class StatusChange(StrictModel):
    status: Literal['ACTIVE', 'RESERVED', 'SOLD']


class IntentChange(StrictModel):
    action: Literal['pause', 'resume', 'renew']
    validity_days: WatchValidityDays | None = None
    duration_not_null = field_validator('validity_days')(classmethod(lambda cls, value: ExpiryUpdate.duration_not_null(value)))

    @model_validator(mode='after')
    def duration_only_for_renewal(self):
        if self.validity_days is not None and self.action != 'renew':
            raise ValueError('请通过续期修改代蹲有效期')
        return self


class WantedCreate(StrictModel):
    validity_days: ValidityDays = 7
    enable_watch: bool = Field(default=False, strict=True)
    watch_validity_days: WatchValidityDays = 14
    title: str = Field(min_length=2, max_length=120)
    description: str = Field(min_length=5, max_length=1000)
    category: str
    budget: Decimal = Field(ge=0, le=999999, decimal_places=2)
    campus: str
    category_valid = field_validator('category')(classmethod(lambda cls, v: ItemCreate.category_valid(v)))
    campus_valid = field_validator('campus')(classmethod(lambda cls, v: ItemCreate.campus_valid(v)))


class WantedWatchCreate(StrictModel):
    validity_days: WatchValidityDays = 14


class ItemUpdate(ExpiryUpdate):
    title: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = Field(default=None, min_length=5, max_length=3000)
    category: str | None = None
    price: Decimal | None = Field(default=None, ge=0, le=999999, max_digits=8, decimal_places=2)
    campus: str | None = None
    condition_grade: str | None = None
    tags: list[str] | None = Field(default=None, max_length=8)
    images: list[str] | None = Field(default=None, max_length=3)

    category_valid = field_validator('category')(classmethod(lambda cls, v: ItemCreate.category_valid(v) if v is not None else None))
    campus_valid = field_validator('campus')(classmethod(lambda cls, v: ItemCreate.campus_valid(v) if v is not None else None))
    condition_valid = field_validator('condition_grade')(classmethod(lambda cls, v: ItemCreate.condition_valid(v) if v is not None else None))
    tags_valid = field_validator('tags')(classmethod(lambda cls, v: ItemCreate.tags_valid(v) if v is not None else None))


class WantedUpdate(ExpiryUpdate):
    title: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = Field(default=None, min_length=5, max_length=1000)
    category: str | None = None
    budget: Decimal | None = Field(default=None, ge=0, le=999999, decimal_places=2)
    campus: str | None = None

    category_valid = field_validator('category')(classmethod(lambda cls, v: ItemCreate.category_valid(v) if v is not None else None))
    campus_valid = field_validator('campus')(classmethod(lambda cls, v: ItemCreate.campus_valid(v) if v is not None else None))


class ReportCreate(StrictModel):
    reason: str = Field(min_length=5, max_length=1000)


class ReviewAction(StrictModel):
    action: Literal['hide', 'restore', 'dismiss']
    note: str = Field(min_length=5, max_length=500)
    confirmed: Literal[True]


class DemoLogin(StrictModel):
    profile: Literal['buyer', 'seller', 'admin']


class EmailCodeRequest(StrictModel):
    email: str = Field(max_length=254)


class EmailCodeVerify(EmailCodeRequest):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=False)
    code: str = Field(pattern=r'^\d{8}$')
    nickname: str = Field(default='', max_length=50)
    campus: str = '不限校区'
    password: SecretStr | None = None
    intent: Literal['register', 'login', 'auto'] = 'auto'

    campus_valid = field_validator('campus')(classmethod(lambda cls, v: ItemCreate.campus_valid(v)))


class PasswordLogin(BaseModel):
    model_config = ConfigDict(extra='forbid')
    email: str = Field(max_length=254)
    password: SecretStr


class PasswordSet(PasswordLogin):
    code: str = Field(pattern=r'^\d{8}$')


class ProfileUpdate(StrictModel):
    email_notifications: bool | None = Field(default=None, strict=True)
    nickname: str | None = Field(default=None, min_length=2, max_length=50)
    campus: str | None = None
    bio: str | None = Field(default=None, max_length=160)
    avatar_color: Literal['sage', 'blue', 'peach', 'lavender'] | None = None

    campus_valid = field_validator('campus')(classmethod(lambda cls, v: ItemCreate.campus_valid(v)))


class ChatMessageCreate(StrictModel):
    body: str = Field(min_length=1, max_length=2000)

    @field_validator('body')
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError('消息不能为空')
        return value.strip()


class ChatReportCreate(StrictModel):
    reason: str = Field(min_length=5, max_length=1000)


class ChatReviewAction(StrictModel):
    action: Literal['hide', 'dismiss']
    note: str = Field(min_length=5, max_length=500)
    confirmed: Literal[True]


class DealAction(StrictModel):
    action: Literal['request', 'reserve', 'decline', 'cancel', 'sold', 'confirm']


class IntentComplete(StrictModel):
    item_id: str | None = None


class AnnouncementCreate(StrictModel):
    title: str = Field(min_length=2, max_length=200)
    body: str = Field(min_length=5, max_length=5000)
    kind: Literal['公告', '更新'] = '公告'


class AnnouncementUpdate(StrictModel):
    title: str | None = Field(default=None, min_length=2, max_length=200)
    body: str | None = Field(default=None, min_length=5, max_length=5000)
    kind: Literal['公告', '更新'] | None = None
    active: bool | None = None


class ItemParseRequest(StrictModel):
    raw: str = Field(min_length=5, max_length=3000)


class ItemDraftImport(StrictModel):
    text: str = Field(min_length=5, max_length=10000)


class ItemDraftUpdate(ExpiryUpdate):
    raw: str | None = Field(default=None, min_length=5, max_length=3000)
    title: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = Field(default=None, min_length=5, max_length=3000)
    category: str | None = None
    price: Decimal | None = Field(default=None, ge=0, le=999999, max_digits=8, decimal_places=2)
    campus: str | None = None
    condition_grade: str | None = None
    tags: list[str] | None = Field(default=None, max_length=8)
    images: list[str] | None = Field(default=None, max_length=3)

    category_valid = field_validator('category')(classmethod(lambda cls, v: ItemCreate.category_valid(v) if v is not None else None))
    campus_valid = field_validator('campus')(classmethod(lambda cls, v: ItemCreate.campus_valid(v) if v is not None else None))
    condition_valid = field_validator('condition_grade')(classmethod(lambda cls, v: ItemCreate.condition_valid(v) if v is not None else None))
    tags_valid = field_validator('tags')(classmethod(lambda cls, v: ItemCreate.tags_valid(v) if v is not None else None))


class ParsedItem(StrictModel):
    title: str | None = Field(default=None, max_length=120)
    description: str | None = Field(default=None, max_length=3000)
    category: str | None = None
    price: Decimal | None = Field(default=None, ge=0, le=999999, decimal_places=2)
    campus: str = '燕园校本部'
    condition_grade: str = '95新'
    tags: list[str] = Field(default_factory=list, max_length=8)
    clarification: str | None = Field(default=None, max_length=500)

    category_valid = field_validator('category')(classmethod(lambda cls, v: ItemCreate.category_valid(v) if v is not None else None))
    campus_valid = field_validator('campus')(classmethod(lambda cls, v: ItemCreate.campus_valid(v)))
    condition_valid = field_validator('condition_grade')(classmethod(lambda cls, v: ItemCreate.condition_valid(v) if v else None))
    tags_valid = field_validator('tags')(classmethod(lambda cls, v: ItemCreate.tags_valid(v)))
