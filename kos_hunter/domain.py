"""Pure domain model and ports. Keep this module vendor and infrastructure free."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable, Protocol, Sequence


class Gender(str, Enum):
    PUTRA = "putra"
    PUTRI = "putri"
    CAMPUR = "campur"


@dataclass(frozen=True)
class KosListing:
    id: str
    name: str
    price: int
    gender: Gender
    location: str = ""
    amenities: frozenset[str] = field(default_factory=frozenset)
    source: str = ""
    url: str = ""


@dataclass(frozen=True)
class TenantProfile:
    gender: Gender
    preferred_amenities: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True)
class SearchCriteria:
    max_price: int
    tenant: TenantProfile
    location: str = ""
    limit: int = 10


@dataclass(frozen=True)
class RankedListing:
    listing: KosListing
    score: int
    reasons: tuple[str, ...]


class ListingSource(Protocol):
    def search(self, criteria: SearchCriteria) -> Iterable[KosListing]: ...


class MessagingPort(Protocol):
    def send(self, recipient: str, message: str) -> None: ...


class NotificationPort(Protocol):
    def notify(self, message: str) -> None: ...


class PersistencePort(Protocol):
    def save_shortlist(self, shortlist: Sequence[RankedListing]) -> None: ...


Repository = PersistencePort


class ClockPort(Protocol):
    def now(self): ...


def is_eligible(listing: KosListing, criteria: SearchCriteria) -> bool:
    if listing.price > criteria.max_price:
        return False
    if criteria.tenant.gender == Gender.PUTRA and listing.gender == Gender.PUTRI:
        return False
    if criteria.tenant.gender == Gender.PUTRI and listing.gender == Gender.PUTRA:
        return False
    if criteria.location and criteria.location.lower() not in listing.location.lower():
        return False
    return True


def rank_listing(listing: KosListing, tenant: TenantProfile) -> RankedListing:
    reasons = []
    score = 0
    labels = {"ac": "AC", "private bathroom": "kamar mandi pribadi", "hot water": "air panas", "wifi": "Wi-Fi", "parking": "parkir", "furnished": "perabot"}
    for amenity in tenant.preferred_amenities:
        if amenity.lower() in {a.lower() for a in listing.amenities}:
            score += 10
            reasons.append(f"Memiliki {labels.get(amenity.lower(), amenity)}")
    if not reasons:
        reasons.append("Memenuhi kriteria dasar")
    return RankedListing(listing, score, tuple(reasons))
