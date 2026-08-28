"""Safe landlord negotiation and explicit human approval gates."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Protocol
from outreach.templates import ask_facilities, negotiate_price, negotiate_extras, walk_away, bot_disclosure

CEILING = 2_000_000

class ApprovalKind(str, Enum):
    SURVEY = "survey"
    BOOKING = "booking"
    CONTRACT = "contract"
    PAYMENT = "payment"
class ApprovalDecision(str, Enum): PENDING="pending"; APPROVED="approved"; REJECTED="rejected"

@dataclass
class ApprovalRequest:
    id: str
    kind: ApprovalKind
    conversation_id: str
    description: str
    created_at: datetime
    decision: ApprovalDecision = ApprovalDecision.PENDING
    decided_at: datetime | None = None
    decided_by: str | None = None

class ApprovalStore(Protocol):
    def save(self, request: ApprovalRequest) -> None: ...
    def get(self, request_id: str) -> ApprovalRequest | None: ...
    def all(self) -> list[ApprovalRequest]: ...

class MemoryApprovalStore:
    def __init__(self): self.requests = {}; self.audit_log = []
    def save(self, request):
        self.requests[request.id] = request
        self.audit_log.append((request.id, request.decision.value, request.decided_by))
    def get(self, request_id): return self.requests.get(request_id)
    def all(self): return list(self.requests.values())

@dataclass
class NegotiationState:
    conversation_id: str
    price: int
    followups: int = 0
    essential_facts: set[str] = field(default_factory=set)
    ended: bool = False

class NegotiationService:
    """Produces drafts; it never sends consequential commitments itself."""
    required_facts = {"availability", "facilities", "recurring_costs", "deposit", "parking"}
    def __init__(self, approvals=None, clock=None):
        self.approvals = approvals or MemoryApprovalStore(); self.clock = clock
    def now(self): return self.clock.now() if self.clock else datetime.now().astimezone()
    def follow_up_questions(self, state: NegotiationState) -> str:
        state.followups += 1
        return ("Boleh saya konfirmasi beberapa hal? Apakah masih tersedia, fasilitasnya apa saja "
                "(AC, kamar mandi dalam, air panas, WiFi), biaya listrik/air rutin berapa, "
                "bagaimana ketentuan deposit, dan apakah parkir motor tersedia?")
    def reply(self, state: NegotiationState, landlord_text: str) -> str:
        text = landlord_text.lower()
        if "bot" in text or "ai" in text or "asisten" in text: return bot_disclosure("saya")
        if state.price > CEILING: return self.end_if_unsafe(state, price=state.price)
        if state.followups < 2 and not self.required_facts.issubset(state.essential_facts): return self.follow_up_questions(state)
        if state.price > 1_700_000: return negotiate_price(f"Rp{state.price:,}", 12)
        return negotiate_extras()
    def end_if_unsafe(self, state, price=None, deposit_before_survey=False, vague=False):
        if (price is not None and price > CEILING) or deposit_before_survey or (vague and state.followups >= 2):
            state.ended = True; return walk_away()
        return "Terima kasih informasinya. Saya pertimbangkan dulu ya."
    def request_approval(self, request_id, kind, conversation_id, description):
        req=ApprovalRequest(request_id, ApprovalKind(kind), conversation_id, description, self.now()); self.approvals.save(req); return req
    def decide(self, request_id, approve: bool, decided_by="user"):
        req=self.approvals.get(request_id)
        if not req: raise KeyError(request_id)
        if req.decision is not ApprovalDecision.PENDING: raise ValueError("approval already decided")
        req.decision=ApprovalDecision.APPROVED if approve else ApprovalDecision.REJECTED; req.decided_at=self.now(); req.decided_by=decided_by; self.approvals.save(req); return req
    def can_commit(self, request_id):
        req=self.approvals.get(request_id); return bool(req and req.decision is ApprovalDecision.APPROVED)
