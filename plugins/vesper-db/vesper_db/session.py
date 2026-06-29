class DbSession:
    """
    Type marker for DI injection of the database session.

    Declare db: DbSession in a service __init__ to receive the
    thread-local SQLAlchemy scoped_session injected by DatabasePlugin:

        from vesper import Injectable
        from vesper_db import DbSession

        @Injectable()
        class UsersService:
            def __init__(self, db: DbSession):
                self.db = db

            def get_all(self):
                return self.db.query(User).all()
    """
    pass
