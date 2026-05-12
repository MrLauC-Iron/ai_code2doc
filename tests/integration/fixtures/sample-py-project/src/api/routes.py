"""API route definitions."""

from fastapi import APIRouter

from src.models.user import User

router = APIRouter()


@router.get("/users", response_model=list[User])
async def get_users() -> list[User]:
    """Return all users."""
    return []


@router.post("/users", response_model=User)
def create_user(user: User) -> User:
    """Create a new user."""
    return user
