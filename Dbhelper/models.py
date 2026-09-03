from dataclasses import dataclass
from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional

from sqlalchemy import (
    BigInteger, Boolean, CheckConstraint, Column, DateTime,
    ForeignKey, Integer, Text, func,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import declarative_base

Base = declarative_base()



class FileType(str, PyEnum):
    pdf     = "pdf"
    csv     = "csv"
    txt     = "txt"
    docx    = "docx"
    image   = "image"
    audio   = "audio"
    video   = "video"
    website = "website"



_file_type_sa = SAEnum(
    FileType,
    name="file_type_enum",
    create_type=False,  
    values_callable=lambda obj: [e.value for e in obj],
)



class UserModel(Base):
    __tablename__ = "users"

    user_id                  = Column("user_id",                  Text, primary_key=True)
    username                 = Column("username",                 Text, unique=True, nullable=False)
    email                    = Column("email",                    Text, unique=True, nullable=True)
    password_hash            = Column("password_hash",            Text, nullable=True)
    refresh_token            = Column("refresh_token",            Text, nullable=True)
    refresh_token_expires_at = Column("refresh_token_expires_at", DateTime(timezone=True), nullable=True)
    is_active                = Column("is_active",                Boolean, nullable=False, server_default="true")
    created_at               = Column("created_at",               DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at               = Column("updated_at",               DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)



class ContentModel(Base):
    __tablename__ = "contents"

    id          = Column("id",          BigInteger, primary_key=True, autoincrement=True)
    content_id  = Column("content_id",  Text, unique=True, nullable=False)
    name        = Column("name",        Text, nullable=False)
    file_type   = Column("file_type",   _file_type_sa, nullable=False, server_default="pdf")
    file_size   = Column("file_size",   BigInteger, nullable=True)
    chunks      = Column("chunks",      Integer, nullable=False, server_default="0")
    inserted_at = Column("inserted_at", DateTime(timezone=True), server_default=func.now(), nullable=False)
    deleted_at  = Column("deleted_at",  DateTime(timezone=True), nullable=True)


class FeedModel(Base):
    __tablename__ = "feeds"

    id          = Column("id",          BigInteger, primary_key=True, autoincrement=True)
    feed_id     = Column("feed_id",     Text, unique=True, nullable=False)
    url         = Column("url",         Text, nullable=False)
    chunks      = Column("chunks",      Integer, nullable=False, server_default="0")
    inserted_at = Column("inserted_at", DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at  = Column("updated_at",  DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    deleted_at  = Column("deleted_at",  DateTime(timezone=True), nullable=True)



class UserMappingModel(Base):
    __tablename__ = "user_mappings"
    __table_args__ = (
        CheckConstraint(
            "(content_id IS NOT NULL AND feed_id IS NULL) OR "
            "(content_id IS NULL AND feed_id IS NOT NULL)",
            name="chk_user_mapping_xor",
        ),
    )

    id         = Column("id",         BigInteger, primary_key=True, autoincrement=True)
    user_id    = Column("user_id",    Text, ForeignKey("users.user_id",          ondelete="CASCADE"), nullable=False)
    content_id = Column("content_id", Text, ForeignKey("contents.content_id",    ondelete="CASCADE"), nullable=True)
    feed_id    = Column("feed_id",    Text, ForeignKey("feeds.feed_id",          ondelete="CASCADE"), nullable=True)
    created_at = Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False)



@dataclass
class User:
    user_id: str
    username: str
    is_active: bool = True
    email: Optional[str] = None
    password_hash: Optional[str] = None
    refresh_token: Optional[str] = None
    refresh_token_expires_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class ContentItem:
    content_id: str
    name: str
    file_type: FileType
    chunks: int
    id: Optional[int] = None
    file_size: Optional[int] = None
    inserted_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None


@dataclass
class FeedItem:
    feed_id: str
    url: str
    chunks: int
    id: Optional[int] = None
    inserted_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None


@dataclass
class UserMapping:
    id: int
    user_id: str
    content_id: Optional[str] = None
    feed_id: Optional[str] = None
    created_at: Optional[datetime] = None
