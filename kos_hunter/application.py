"""Use cases coordinating pure domain with injected ports."""
from __future__ import annotations
from typing import Iterable, Sequence
from .domain import ContactStatus, LandlordContact, ListingSource, PersistencePort, RankedListing, SearchCriteria, is_eligible, normalize_phone, rank_listing


class SearchFacade:
    def __init__(self, sources: Sequence[ListingSource], persistence: PersistencePort | None = None, owner_id: str = "local"):
        self.sources = tuple(sources)
        self.persistence = persistence
        self.owner_id = owner_id

    def search(self, criteria: SearchCriteria) -> list[RankedListing]:
        listings = [listing for source in self.sources for listing in source.search(criteria)]
        run_id = self.persistence.start_search(self.owner_id, criteria) if self.persistence and hasattr(self.persistence, "start_search") else None
        shortlist = [rank_listing(x, criteria.tenant) for x in listings if is_eligible(x, criteria)]
        shortlist.sort(key=lambda item: item.score, reverse=True)
        shortlist = shortlist[: criteria.limit]
        if self.persistence:
            if run_id is not None:
                self.persistence.save_search_run(run_id, listings, shortlist)
            else:
                self.persistence.save_shortlist(shortlist)
        return shortlist

    def enrich_contacts(self, shortlist: Sequence[RankedListing], contact_source) -> dict[str, LandlordContact]:
        """Retrieve contacts only for shortlisted listings and persist locally."""
        contacts = {}
        for ranked in shortlist:
            try:
                raw = contact_source.get_contact(ranked.listing)
                if not raw:
                    contact = LandlordContact(ContactStatus.MISSING, source_links=ranked.listing.source_links)
                else:
                    try: phone = normalize_phone(raw)
                    except ValueError: contact = LandlordContact(ContactStatus.MALFORMED, source_links=ranked.listing.source_links)
                    else:
                        prior = contacts.get(phone)
                        links = tuple(dict.fromkeys((prior.source_links if prior else ()) + ranked.listing.source_links + ((ranked.listing.url,) if ranked.listing.url else ())))
                        contact = LandlordContact(ContactStatus.AVAILABLE, phone, links)
                        contacts[phone] = contact
                        continue
            except Exception:
                contact = LandlordContact(ContactStatus.INACCESSIBLE, source_links=ranked.listing.source_links)
            contacts[f"listing:{ranked.listing.source}:{ranked.listing.id}"] = contact
        if self.persistence and hasattr(self.persistence, 'save_contacts'):
            self.persistence.save_contacts([(r, c) for k, c in contacts.items() for r in shortlist if k.endswith(r.listing.id) or (c.phone and k == c.phone)])
        return contacts

    def run(self, criteria: SearchCriteria) -> list[RankedListing]:
        return self.search(criteria)
