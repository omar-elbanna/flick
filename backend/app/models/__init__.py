"""ORM model package — import side effects register all tables with Base.metadata."""

from app.models.group import (
    Group,
    GroupMember,
    GroupMemberRole,
    GroupSession,
    GroupSessionStatus,
    SessionVote,
    VoteChoice,
)
from app.models.movie import Movie
from app.models.rating import Rating
from app.models.taste_profile import UserTasteProfile
from app.models.user import RefreshToken, User
from app.models.watchlist import WatchlistItem

__all__ = [
    "Group",
    "GroupMember",
    "GroupMemberRole",
    "GroupSession",
    "GroupSessionStatus",
    "Movie",
    "Rating",
    "RefreshToken",
    "SessionVote",
    "User",
    "UserTasteProfile",
    "VoteChoice",
    "WatchlistItem",
]
