from sqlalchemy import Boolean, Column, Integer, String, Enum
from .database import Base
import enum

class UserRole(str, enum.Enum):
    ADMIN = "admin"
    VIP = "vip"
    NORMAL = "normal"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    role = Column(Enum(UserRole), default=UserRole.NORMAL)
    is_active = Column(Boolean, default=True)
