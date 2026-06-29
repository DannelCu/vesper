from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """
    Base class for all vesper-db models.

    Define your models by inheriting from this class:

        from vesper_db import Base
        from sqlalchemy.orm import Mapped, mapped_column

        class User(Base):
            __tablename__ = "users"
            id: Mapped[int] = mapped_column(primary_key=True)
            email: Mapped[str]

    All models defined anywhere in the project are discovered automatically
    when DatabasePlugin calls Base.metadata.create_all() at startup.
    """
    pass
