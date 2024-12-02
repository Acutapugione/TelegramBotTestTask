from datetime import datetime
from typing import Iterable
from pydantic import ValidationError
from sqlmodel import (
    select,
)

from shared.enums import EUserStatus
from . import User, Whitelist, DBConfig


class UserCRUD:
    model = User
    config = DBConfig

    @classmethod
    def _get_item(cls, pk: int):
        return cls.config.SESSION.get_one(cls.model, pk)

    @classmethod
    def update_user_status(cls, user_id: int, status: EUserStatus):
        item = cls._get_item(user_id)
        item.status = status
        cls.config.SESSION.add(item)
        cls.config.SESSION.commit()

    @classmethod
    def update_white_list(cls, user_id, *white_list: tuple[Whitelist]):
        item = cls._get_item(user_id)
        item.white_list.extend(white_list)
        cls.config.SESSION.add(item)
        cls.config.SESSION.commit()

    @classmethod
    def update_applications_sent(cls, user_id, applications_sent):
        item = cls._get_item(user_id)
        item.applications_sent = applications_sent
        cls.config.SESSION.add(item)
        cls.config.SESSION.commit()

    @classmethod
    def load_users(cls):
        return {
            user.id: user.model_dump()
            for user in cls.config.SESSION.scalars(select(cls.model)).all()
        }

    @classmethod
    def register_user(cls, user_id):
        try:
            item = cls.model.model_validate(
                {
                    "id": user_id,
                    "registration_date": str(datetime.now()),
                    "status": EUserStatus.ADMIN,
                    "applications_sent": 0,
                    "applications_per_url": {},
                }
            )
            cls.config.SESSION.add(item)
            cls.config.SESSION.commit()
        except ValidationError as ve:
            print(f"Validation error: {ve}")
        except Exception as e:
            print(f"Unspecified exception: {e}")
