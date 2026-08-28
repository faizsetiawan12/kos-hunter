"""Vendor-neutral search domain."""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
import re
from typing import Iterable, Protocol, Sequence
class Gender(str, Enum): PUTRA='putra'; PUTRI='putri'; CAMPUR='campur'
class ContactStatus(str, Enum): AVAILABLE='AVAILABLE'; MISSING='MISSING'; MALFORMED='MALFORMED'; INACCESSIBLE='INACCESSIBLE'
@dataclass(frozen=True)
class LandlordContact:
    status: ContactStatus
    phone: str = ''
    source_links: tuple[str, ...] = ()

def normalize_phone(value: str) -> str:
    """Normalize Indonesian mobile numbers to canonical +62 E.164 form."""
    if not isinstance(value, str): raise ValueError('phone must be text')
    digits = re.sub(r'[^0-9]', '', value)
    if digits.startswith('08'): digits = '62' + digits[1:]
    elif digits.startswith('8'): digits = '62' + digits
    if not digits.startswith('62') or not (10 <= len(digits) <= 14) or not digits[2:].startswith('8'):
        raise ValueError('malformed Indonesian phone number')
    return '+' + digits
@dataclass(frozen=True)
class KosListing:
    id: str; name: str; price: int; gender: Gender; location: str=''; amenities: frozenset[str]=field(default_factory=frozenset); source: str=''; url: str=''; available: bool|None=None; source_links: tuple[str,...]=()
@dataclass(frozen=True)
class TenantProfile: gender: Gender; preferred_amenities: frozenset[str]=frozenset({'AC','private bathroom','hot water','wifi'})
@dataclass(frozen=True)
class SearchCriteria: max_price: int; tenant: TenantProfile; location: str=''; limit: int=10
@dataclass(frozen=True)
class RankedListing: listing: KosListing; score: int; reasons: tuple[str,...]
class ListingSource(Protocol):
 def search(self, criteria: SearchCriteria) -> Iterable[KosListing]: ...
class PersistencePort(Protocol):
 def save_shortlist(self, shortlist: Sequence[RankedListing]) -> None: ...
 def save_contacts(self, contacts: Sequence[tuple[RankedListing, LandlordContact]]) -> None: ...
def is_eligible(x, c): return x.price <= c.max_price and x.gender != Gender.PUTRI and (not c.location or c.location.lower() in x.location.lower())
def rank_listing(x, tenant):
 score=5 if x.available is True else 0; reasons=['Tersedia'] if x.available is True else []
 for a in tenant.preferred_amenities:
  if a.lower() in {v.lower() for v in x.amenities}: score+=10; reasons.append('Memiliki '+a)
 return RankedListing(x,score,tuple(reasons or ['Memenuhi kriteria dasar']))
