from sqlmodel import SQLModel, Field, Relationship
from shared.enums import EUserStatus


class UserWhiteLink(SQLModel, table=True):
    user_id: int | None = Field(default=None, foreign_key="user.id", primary_key=True)
    whitelist_id: int | None = Field(
        default=None, foreign_key="whitelist.id", primary_key=True
    )


class Whitelist(SQLModel, table=True):
    id: int = Field(primary_key=True)
    url: str = Field(unique=True)
    users: list["User"] = Relationship(
        back_populates="white_list", link_model=UserWhiteLink
    )


class User(SQLModel, table=True):
    id: int = Field(primary_key=True)
    registration_date: str
    status: EUserStatus = Field(default=EUserStatus.DEMO)
    applications_sent: int
    white_list: list["Whitelist"] = Relationship(
        back_populates="users", link_model=UserWhiteLink
    )
