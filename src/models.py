"""
Database models using SQLAlchemy Async ORM.
Tables: Users, Categories, Transactions
"""

from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional, List

from sqlalchemy import BigInteger, String, DateTime, Float, ForeignKey, Enum, Text, JSON
from sqlalchemy.ext.asyncio import AsyncAttrs, create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class TransactionType(PyEnum):
    """Enum for transaction types: EXPENSE (Chi) or INCOME (Thu)"""
    EXPENSE = "EXPENSE"
    INCOME = "INCOME"


class Base(AsyncAttrs, DeclarativeBase):
    """Base class for all models"""
    pass


class User(Base):
    """User model - supports both Telegram and Zalo"""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    telegram_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, unique=True)
    zalo_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, unique=True)
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, unique=True)
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    # Relationships
    transactions: Mapped[List["Transaction"]] = relationship(back_populates="user", lazy="selectin")

    def __repr__(self) -> str:
        return f"<User(id={self.id}, telegram={self.telegram_id}, zalo={self.zalo_id})>"


class Category(Base):
    """Transaction category model with keywords for auto-detection"""
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    keywords: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Comma-separated keywords
    type: Mapped[TransactionType] = mapped_column(
        Enum(TransactionType), 
        default=TransactionType.EXPENSE
    )

    # Relationships
    transactions: Mapped[List["Transaction"]] = relationship(back_populates="category", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Category(id={self.id}, name={self.name}, type={self.type.value})>"

    def get_keywords_list(self) -> List[str]:
        """Return keywords as a list"""
        if not self.keywords:
            return []
        return [kw.strip().lower() for kw in self.keywords.split(",")]


class Transaction(Base):
    """Financial transaction model"""
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    category_id: Mapped[Optional[int]] = mapped_column(ForeignKey("categories.id"), nullable=True)
    note: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    date: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    raw_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Original user message

    # Relationships
    user: Mapped["User"] = relationship(back_populates="transactions", lazy="selectin")
    category: Mapped[Optional["Category"]] = relationship(back_populates="transactions", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Transaction(id={self.id}, amount={self.amount}, note={self.note})>"


class UserKeyword(Base):
    """User-specific keyword to category mapping for learning"""
    __tablename__ = "user_keywords"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    keyword: Mapped[str] = mapped_column(String(100), nullable=False)  # Normalized keyword
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), nullable=False)
    count: Mapped[int] = mapped_column(default=1)  # How many times this mapping was used
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)

    def __repr__(self) -> str:
        return f"<UserKeyword(user={self.user_id}, keyword={self.keyword}, category={self.category_id})>"


# Database engine and session factory
engine = None
async_session_factory = None


async def init_db(db_url: str) -> None:
    """Initialize database engine and create all tables"""
    global engine, async_session_factory
    
    engine = create_async_engine(db_url, echo=False)
    async_session_factory = async_sessionmaker(engine, expire_on_commit=False)
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncSession:
    """Get a new database session"""
    if async_session_factory is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return async_session_factory()


async def seed_default_categories(session: AsyncSession) -> None:
    """Seed default categories if they don't exist"""
    from sqlalchemy import select
    
    result = await session.execute(select(Category).limit(1))
    if result.scalar_one_or_none() is not None:
        return  # Categories already exist
    
    default_categories = [
        # === Chi tiêu - sinh hoạt ===
        Category(
            name="Chợ/Siêu thị",
            keywords="chợ,siêu thị,big c,coopmart,winmart,lotte,aeon,đi chợ,thực phẩm,rau,thịt,cá,trứng,gạo",
            type=TransactionType.EXPENSE
        ),
        Category(
            name="Ăn uống",
            keywords="cafe,cà phê,coffee,cơm,phở,bún,ăn,uống,trà sữa,milk tea,bia,rượu,nhậu,quán,restaurant,grab food,shopee food,bữa sáng,bữa trưa,bữa tối,ăn sáng,ăn trưa,ăn tối,bánh mì",
            type=TransactionType.EXPENSE
        ),
        Category(
            name="Di chuyển",
            keywords="xăng,grab,uber,taxi,gửi xe,parking,xe máy,ô tô,car,bike,bus,xe buýt,đi lại,vé tàu,vé xe,be,gojek",
            type=TransactionType.EXPENSE
        ),
        # === Chi phí phát sinh ===
        Category(
            name="Cho vay",
            keywords="cho vay,cho mượn,trả nợ,nợ",
            type=TransactionType.EXPENSE
        ),
        Category(
            name="Mua sắm",
            keywords="quần áo,giày dép,đồ điện tử,shopee,lazada,tiki,amazon,mua,shopping,iphone,macbook,laptop",
            type=TransactionType.EXPENSE
        ),
        Category(
            name="Giải trí",
            keywords="phim,movie,game,netflix,spotify,youtube,du lịch,travel,karaoke,bar,club,nhạc,concert",
            type=TransactionType.EXPENSE
        ),
        Category(
            name="Làm đẹp",
            keywords="mỹ phẩm,spa,nail,tóc,cắt tóc,skincare,makeup,son,kem,dưỡng",
            type=TransactionType.EXPENSE
        ),
        Category(
            name="Sức khỏe",
            keywords="thuốc,bệnh viện,khám bệnh,doctor,pharmacy,gym,thể dục,bảo hiểm y tế,vitamin",
            type=TransactionType.EXPENSE
        ),
        Category(
            name="Từ thiện",
            keywords="từ thiện,quyên góp,donate,ủng hộ,giúp đỡ",
            type=TransactionType.EXPENSE
        ),
        # === Chi phí cố định ===
        Category(
            name="Hóa đơn",
            keywords="điện,nước,internet,wifi,gas,4g,5g,điện thoại,bill,hóa đơn,tiền nhà,thuê nhà,rent",
            type=TransactionType.EXPENSE
        ),
        Category(
            name="Người thân",
            keywords="bố,mẹ,cha,ba,má,con,vợ,chồng,anh,chị,em,gia đình,biếu,tặng,cho,người yêu,người iu,bạn gái,bạn trai,ông,bà",
            type=TransactionType.EXPENSE
        ),
        # === Đầu tư - tiết kiệm ===
        Category(
            name="Đầu tư",
            keywords="đầu tư,invest,cổ phiếu,stock,crypto,bitcoin,chứng khoán,tiết kiệm,gửi tiết kiệm",
            type=TransactionType.EXPENSE
        ),
        Category(
            name="Học tập",
            keywords="sách,book,khóa học,course,học phí,tuition,udemy,coursera,học",
            type=TransactionType.EXPENSE
        ),
        # === Thu nhập ===
        Category(
            name="Lương",
            keywords="lương,salary,income,thu nhập,tiền công,wage",
            type=TransactionType.INCOME
        ),
        Category(
            name="Thưởng",
            keywords="thưởng,bonus",
            type=TransactionType.INCOME
        ),
        Category(
            name="Thu khác",
            keywords="được cho,được tặng,trả nợ,thu hồi",
            type=TransactionType.INCOME
        ),
        # === Khác ===
        Category(
            name="Khác",
            keywords="",
            type=TransactionType.EXPENSE
        ),
    ]
    
    for cat in default_categories:
        session.add(cat)
    await session.commit()
