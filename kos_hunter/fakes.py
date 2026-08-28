from __future__ import annotations
from datetime import datetime, timezone
from .domain import KosListing, RankedListing, SearchCriteria

class FakeListingSource:
    def __init__(self, listings=()): self.listings = list(listings)
    def search(self, criteria: SearchCriteria): return list(self.listings)

class FakeMessagingAdapter:
    def __init__(self): self.messages = []
    def send(self, recipient, message): self.messages.append((recipient, message))

class FakeNotificationAdapter:
    def __init__(self): self.notifications = []
    def notify(self, message): self.notifications.append(message)

class FakePersistenceAdapter:
    def __init__(self): self.shortlists = []
    def save_shortlist(self, shortlist): self.shortlists.append(list(shortlist))

class FakeClock:
    def __init__(self, current=None): self.current = current or datetime.now(timezone.utc)
    def now(self): return self.current
