import abc
from types import TracebackType

from sqlalchemy.orm import Session, sessionmaker

from app.repository import AccountRepository


class AbstractUnitOfWork(abc.ABC):
    """
    Abstract Base Class defining the contract for our Unit of Work.
    This allows us to easily swap out the SQLAlchemy implementation
    for a Mock implementation in unit tests.
    """

    accounts: AccountRepository

    def __enter__(self) -> "AbstractUnitOfWork":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if exc_type:
            self.rollback()
        else:
            self.commit()

    @abc.abstractmethod
    def commit(self) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def rollback(self) -> None:
        raise NotImplementedError


class SqlAlchemyUnitOfWork(AbstractUnitOfWork):
    """
    Production-grade SQLAlchemy Implementation of the Unit of Work.
    Manages the session lifecycle (creation, commit, rollback, close).
    """

    def __init__(self, session_factory: sessionmaker) -> None:
        self.session_factory = session_factory

    def __enter__(self) -> "SqlAlchemyUnitOfWork":
        self.session: Session = self.session_factory()
        # Instantiate repositories bound to this specific session
        self.accounts = AccountRepository(self.session)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        # Execute commit or rollback
        super().__exit__(exc_type, exc_val, traceback)
        # Ensure the session is always closed to return the connection to the pool
        self.session.close()

    def commit(self) -> None:
        self.session.commit()

    def rollback(self) -> None:
        self.session.rollback()
