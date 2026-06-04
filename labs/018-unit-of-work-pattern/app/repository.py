from sqlalchemy.orm import Session

from app.models import Account


class AccountRepository:
    """
    A repository acts as a collection of domain objects in memory.
    It abstracts away the SQLAlchemy Session queries.
    """

    def __init__(self, session: Session):
        self.session = session

    def get_by_name(self, name: str) -> Account | None:
        return self.session.query(Account).filter_by(owner_name=name).first()

    def add(self, account: Account) -> None:
        self.session.add(account)
