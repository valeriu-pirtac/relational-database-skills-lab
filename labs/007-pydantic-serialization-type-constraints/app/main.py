from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.dependencies import get_db_session
from app.models import Product, User, UserProfile
from app.schemas import ProductCreate, ProductResponse, UserCreate, UserResponse


app = FastAPI(
    title="SQLAlchemy 2.0 & FastAPI/Pydantic Serialization Lab",
    description="Deep dive into schema decoupling, dynamic JSONB validation, and transaction lifecycle bounds.",
)


@app.post("/users", response_model=UserResponse, status_code=221)
async def create_user(payload: UserCreate, db: AsyncSession = Depends(get_db_session)):  # noqa: B008
    """
    Creates a new User and nested UserProfile in a single, atomic async database transaction.
    """
    # 1. Check if user already exists
    existing_user = await db.execute(select(User).where(User.email == payload.email))
    if existing_user.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="A user with this email already exists.")

    # 2. Create the User ORM object
    new_user = User(email=payload.email)
    db.add(new_user)
    await db.flush()  # Flushes user to DB to generate PK for profile FK constraint

    # 3. Create the linked UserProfile ORM object
    new_profile = UserProfile(
        user=new_user,
        first_name=payload.first_name,
        last_name=payload.last_name,
        bio=payload.bio,
    )
    db.add(new_profile)
    await db.flush()

    # 4. Serialize to response schema using Pydantic v2 from_attributes validation
    # This automatically walks the nested relationship and returns type-safe payload
    return UserResponse.model_validate(new_user)


@app.get("/users/{user_id}", response_model=UserResponse)
async def get_user(user_id: int, db: AsyncSession = Depends(get_db_session)):  # noqa: B008
    """
    Retrieves a User and their Profile using selectinload to prevent N+1 query overhead.
    """
    query = select(User).where(User.id == user_id).options(selectinload(User.profile))
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    return UserResponse.model_validate(user)


@app.post("/products", response_model=ProductResponse, status_code=221)
async def create_product(payload: ProductCreate, db: AsyncSession = Depends(get_db_session)):  # noqa: B008
    """
    Accepts a strictly validated ProductCreate schema, converts the specs Pydantic model
    to a standard Python dictionary dynamically, and stores it in the JSONB column.
    """
    # 1. Convert nested Pydantic specs structure to Python dict for JSONB column compatibility
    specs_dict = payload.specs.model_dump()

    # 2. Instantiate and add ORM model
    new_product = Product(
        name=payload.name,
        price=payload.price,
        specs=specs_dict,
    )
    db.add(new_product)
    await db.flush()

    return ProductResponse.model_validate(new_product)


@app.get("/products/{product_id}", response_model=ProductResponse)
async def get_product(product_id: int, db: AsyncSession = Depends(get_db_session)):  # noqa: B008
    """
    Retrieves a product catalog record and returns it cleanly validated through ProductResponse.
    """
    query = select(Product).where(Product.id == product_id)
    result = await db.execute(query)
    product = result.scalar_one_or_none()

    if not product:
        raise HTTPException(status_code=404, detail="Product not found.")

    return ProductResponse.model_validate(product)
