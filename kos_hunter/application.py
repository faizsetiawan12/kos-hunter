"""Use cases coordinating pure domain with injected ports."""
from __future__ import annotations
from typing import Iterable, Sequence
from .domain import ListingSource, PersistencePort, RankedListing, SearchCriteria, is_eligible, rank_listing


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

    def run(self, criteria: SearchCriteria) -> list[RankedListing]:
        return self.search(criteria)
