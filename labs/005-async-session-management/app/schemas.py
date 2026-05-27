from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class UserSchema(BaseModel):
    """Pydantic model for User details."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str
    created_at: datetime


class BankAccountSchema(BaseModel):
    """Pydantic model for BankAccount details."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    account_number: str
    balance: Decimal
    created_at: datetime


class BankAccountWithUserSchema(BaseModel):
    """
    Pydantic model for BankAccount with nested User details.
    Accessing the user relationship will trigger MissingGreenlet if it is not eager loaded.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    account_number: str
    balance: Decimal
    created_at: datetime
    user: UserSchema


class TransferRequest(BaseModel):
    """Pydantic schema representing a funds transfer request."""

    from_account: str = Field(..., description="Source account number")
    to_account: str = Field(..., description="Destination account number")
    amount: Decimal = Field(..., gt=0, description="Amount to transfer")


class TransferResponse(BaseModel):
    """Pydantic schema representing the outcome of a funds transfer."""

    status: str
    message: str
    amount: Decimal
    from_balance: Decimal
    to_balance: Decimal
