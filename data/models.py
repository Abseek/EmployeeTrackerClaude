from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Employee:
    id: str
    username: str
    display_name: str
    email: str
    role: str  # "admin" | "employee"
    password_hash: str
    created_at: str
    updated_at: str
    is_active: bool = True

    def is_admin(self) -> bool:
        return self.role == "admin"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "username": self.username,
            "display_name": self.display_name,
            "email": self.email,
            "role": self.role,
            "password_hash": self.password_hash,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "is_active": self.is_active,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Employee":
        return cls(
            id=d["id"],
            username=d["username"],
            display_name=d["display_name"],
            email=d["email"],
            role=d["role"],
            password_hash=d["password_hash"],
            created_at=d["created_at"],
            updated_at=d["updated_at"],
            is_active=d.get("is_active", True),
        )


@dataclass
class ActivityBucket:
    minute_bucket: str       # ISO format floored to minute
    keystrokes: int = 0
    mouse_clicks: int = 0
    mouse_scroll_ticks: int = 0
    mouse_distance_px: float = 0.0
    active_window_title: str = ""
    idle_seconds: int = 0
    productivity_score: float = 0.0

    def to_dict(self) -> dict:
        return {
            "minute_bucket": self.minute_bucket,
            "keystrokes": self.keystrokes,
            "mouse_clicks": self.mouse_clicks,
            "mouse_scroll_ticks": self.mouse_scroll_ticks,
            "mouse_distance_px": round(self.mouse_distance_px, 1),
            "active_window_title": self.active_window_title,
            "idle_seconds": self.idle_seconds,
            "productivity_score": self.productivity_score,
        }
