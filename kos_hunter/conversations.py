"""Conversation tracking, inbound correlation, verified facts, and safe follow-up."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timedelta, time
from enum import Enum
from typing import Protocol

class ConversationOutcome(str, Enum):
    UNAVAILABLE='UNAVAILABLE'; REPLIED='REPLIED'; NO_REPLY='NO_REPLY'; FAILED='FAILED'; CANCELLED='CANCELLED'; COMPLETED='COMPLETED'

@dataclass(frozen=True)
class ConversationFact:
    key: str
    value: str
    verified_at: datetime
    source: str = 'conversation'

@dataclass
class Conversation:
    id: str
    candidate_id: str
    listing_id: str
    listing_title: str
    price: int
    source_link: str
    recipient: str
    outbound: list[str] = field(default_factory=list)
    inbound: list[str] = field(default_factory=list)
    facts: list[ConversationFact] = field(default_factory=list)
    outcome: ConversationOutcome | None = None
    last_outbound_at: datetime | None = None
    follow_up_sent: bool = False

@dataclass(frozen=True)
class InboundMessage:
    recipient: str
    text: str
    received_at: datetime

class NotificationPort(Protocol):
    def notify(self, message: str) -> None: ...

class ConversationStore(Protocol):
    def save(self, conversation: Conversation) -> None: ...
    def get(self, conversation_id: str) -> Conversation | None: ...
    def by_recipient(self, recipient: str) -> Conversation | None: ...

class MemoryConversationStore:
    def __init__(self): self.items: dict[str, Conversation] = {}
    def save(self, conversation): self.items[conversation.id] = conversation
    def get(self, conversation_id): return self.items.get(conversation_id)
    def by_recipient(self, recipient):
        matches=[c for c in self.items.values() if c.recipient == recipient and c.outcome not in (ConversationOutcome.CANCELLED, ConversationOutcome.COMPLETED)]
        return matches[-1] if matches else None

class ConversationService:
    def __init__(self, store=None, notification: NotificationPort | None = None, clock=None):
        self.store=store or MemoryConversationStore(); self.notification=notification; self.clock=clock
    def now(self): return self.clock.now() if self.clock else datetime.now().astimezone()
    def start(self, conversation_id, candidate_id, listing, recipient, outbound_at=None):
        link = listing.url or (listing.source_links[0] if getattr(listing, 'source_links', ()) else '')
        c=Conversation(conversation_id,candidate_id,listing.id,listing.name,listing.price,link,recipient)
        c.last_outbound_at=outbound_at or self.now(); c.outbound.append('sent'); self.store.save(c); return c
    def record_inbound(self, message: InboundMessage) -> Conversation:
        c=self.store.by_recipient(message.recipient)
        if not c: raise KeyError(f'no active conversation for {message.recipient}')
        c.inbound.append(message.text); c.outcome=ConversationOutcome.REPLIED; self.store.save(c)
        if self.notification:
            self.notification.notify(f"Balasan landlord: {c.listing_title} — Rp{c.price:,}/bulan\n{c.source_link}\nPercakapan {c.id}:\n{message.text}")
        return c
    def add_verified_fact(self, conversation_id, key, value, verified_at=None):
        c=self._get(conversation_id); c.facts.append(ConversationFact(key,value,verified_at or self.now())); self.store.save(c); return c
    def mark_outcome(self, conversation_id, outcome):
        c=self._get(conversation_id); c.outcome=ConversationOutcome(outcome); self.store.save(c); return c
    def follow_up_eligible(self, conversation_id, at=None):
        c=self._get(conversation_id); now=at or self.now()
        return (c.outcome in (None, ConversationOutcome.NO_REPLY) and not c.inbound and not c.follow_up_sent and c.last_outbound_at is not None and now-c.last_outbound_at >= timedelta(hours=48) and time(8)<=now.time().replace(tzinfo=None)<time(20))

    def eligible_follow_ups(self, at=None):
        now=at or self.now()
        return [c for c in self.store.items.values() if self.follow_up_eligible(c.id, now)] if hasattr(self.store, 'items') else []
    def send_follow_up(self, conversation_id, messaging, at=None):
        if not self.follow_up_eligible(conversation_id,at): raise ValueError('conversation is not eligible for follow-up')
        c=self._get(conversation_id); messaging.send(c.recipient, f"Halo, izin follow-up terkait {c.listing_title}. Apakah masih tersedia?")
        c.follow_up_sent=True; c.outcome=ConversationOutcome.NO_REPLY; c.last_outbound_at=at or self.now(); self.store.save(c); return c
    def _get(self, cid):
        c=self.store.get(cid)
        if not c: raise KeyError(cid)
        return c
