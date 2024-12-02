from sqlmodel import SQLModel, Session, create_engine


class DBConfig:
    ENGINE = create_engine("sqlite:///users.db", echo=True)
    SESSION = Session(bind=ENGINE)

    @classmethod
    def drop(cls):
        SQLModel.metadata.drop_all(cls.ENGINE)

    @classmethod
    def create(cls):
        SQLModel.metadata.create_all(cls.ENGINE)
