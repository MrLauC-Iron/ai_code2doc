"""User model definition."""

from pydantic import BaseModel


class User(BaseModel):
    """A simple user model."""

    name: str
    email: str
    age: int = 0

    @property
    def display_name(self) -> str:
        """Return a display-friendly name."""
        return f"{self.name} <{self.email}>"
