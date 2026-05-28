from pydantic import BaseModel, ConfigDict, EmailStr, Field


# ==========================================
# User & Profile Decoupled API Schemas
# ==========================================


class UserCreate(BaseModel):
    """API Request schema used during user registration."""

    email: EmailStr
    first_name: str = Field(..., min_length=1, max_length=50, description="User's first name")
    last_name: str = Field(..., min_length=1, max_length=50, description="User's last name")
    bio: str | None = Field(None, max_length=500, description="Optional brief biography")


class ProfileResponse(BaseModel):
    """Nested Response schema representing user profile details."""

    model_config = ConfigDict(from_attributes=True)

    first_name: str
    last_name: str
    bio: str | None


class UserResponse(BaseModel):
    """API Response schema representing the complete User, including nested Profile relationships."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    is_active: bool
    profile: ProfileResponse | None = None


# ==========================================
# Dynamic JSONB Column Validation Schemas
# ==========================================


class Dimensions(BaseModel):
    """Pydantic schema representing the physical dimensions of a product."""

    width: float = Field(..., gt=0, description="Width in cm")
    height: float = Field(..., gt=0, description="Height in cm")
    depth: float = Field(..., gt=0, description="Depth in cm")


class ProductSpecs(BaseModel):
    """Enforces strict structural and type constraints on the Product's specs JSONB document."""

    weight_kg: float = Field(..., gt=0, description="Weight of the product in kilograms")
    warranty_years: int = Field(..., ge=0, le=10, description="Warranty coverage in years")
    dimensions: Dimensions = Field(..., description="Physical dimensions of the item")
    tags: list[str] = Field(default_factory=list, description="Categorization tags")


class ProductCreate(BaseModel):
    """API Request schema used during product catalog registration."""

    name: str = Field(..., min_length=1, max_length=100)
    price: float = Field(..., gt=0)
    specs: ProductSpecs = Field(..., description="Strict specs JSONB block")


class ProductResponse(BaseModel):
    """API Response schema representing a verified catalog item."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    price: float
    specs: ProductSpecs
