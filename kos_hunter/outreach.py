"""Approval-gated, rate-limited first-contact outreach."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from enum import Enum
from typing import Protocol
from outreach.templates import KosInfo, opening

class OutreachState(str, Enum):
    PENDING="PENDING"; READY="READY"; SENDING="SENDING"; SENT="SENT"; FAILED="FAILED"; CANCELLED="CANCELLED"

class MessagingPort(Protocol):
    def send(self, recipient: str, message: str) -> None: ...

@dataclass
class OutreachJob:
    id: str
    recipient: str
    message: str
    listing_id: str
    state: OutreachState = OutreachState.PENDING
    created_at: datetime | None = None
    updated_at: datetime | None = None
    sent_at: datetime | None = None
    error: str | None = None

class OutreachStore(Protocol):
    def save(self, job: OutreachJob) -> None: ...
    def get(self, job_id: str) -> OutreachJob | None: ...
    def all(self) -> list[OutreachJob]: ...

class MemoryOutreachStore:
    def __init__(self): self.jobs: dict[str, OutreachJob] = {}
    def save(self, job): self.jobs[job.id] = job
    def get(self, job_id): return self.jobs.get(job_id)
    def all(self): return list(self.jobs.values())

class OutreachError(RuntimeError): pass
class ApprovalRequired(OutreachError): pass
class OutreachLimitsExceeded(OutreachError): pass

class OutreachService:
    def __init__(self, messaging: MessagingPort, store: OutreachStore | None = None, clock=None, tenant_name="saya"):
        self.messaging, self.store, self.clock, self.tenant_name = messaging, store or MemoryOutreachStore(), clock, tenant_name
    def now(self):
        value = self.clock.now() if self.clock else datetime.now().astimezone()
        return value
    def queue(self, candidates) -> list[OutreachJob]:
        """Create truthful drafts for shortlisted candidates with valid contacts."""
        jobs=[]; now=self.now()
        for candidate in candidates:
            contact = getattr(candidate, "contact", None) or getattr(candidate, "phone", "")
            listing = getattr(candidate, "listing", candidate)
            if not contact: continue
            jid = f"{getattr(listing,'source','local')}:{listing.id}:{contact}"
            job=OutreachJob(jid, contact, opening(KosInfo(listing.name, f"Rp{listing.price:,}", listing.location), self.tenant_name), listing.id, created_at=now, updated_at=now)
            self.store.save(job); jobs.append(job)
        return jobs
    def approve(self, job_ids):
        jobs=[]
        for jid in job_ids:
            job=self.store.get(jid)
            if not job: raise OutreachError(f"unknown job: {jid}")
            if job.state in (OutreachState.PENDING, OutreachState.FAILED): job.state=OutreachState.READY; job.error=None; job.updated_at=self.now(); self.store.save(job)
            jobs.append(job)
        return jobs
    def cancel(self, job_ids):
        for jid in job_ids:
            job=self.store.get(jid)
            if job and job.state not in (OutreachState.SENT, OutreachState.CANCELLED): job.state=OutreachState.CANCELLED; job.updated_at=self.now(); self.store.save(job)
    def send_approved(self, job_ids):
        now=self.now(); self._check_hours(now)
        jobs=[self.store.get(x) for x in job_ids]
        if any(j is None for j in jobs): raise OutreachError("unknown job")
        if any(j.state != OutreachState.READY for j in jobs): raise ApprovalRequired("only explicitly approved drafts can be sent")
        sent_today=sum(1 for j in self.store.all() if j.state==OutreachState.SENT and j.sent_at and j.sent_at.date()==now.date())
        if sent_today + len(jobs)>15: raise OutreachLimitsExceeded("maximum 15 new landlords per day")
        last=max((j.sent_at for j in self.store.all() if j.sent_at and j.sent_at.date()==now.date()), default=None)
        for job in jobs:
            current=self.now()
            if last and current-last < timedelta(minutes=3): raise OutreachLimitsExceeded("minimum 3 minutes between messages")
            job.state=OutreachState.SENDING; job.updated_at=current; self.store.save(job)
            try: self.messaging.send(job.recipient, job.message)
            except Exception as exc: job.state=OutreachState.FAILED; job.error=str(exc); job.updated_at=self.now(); self.store.save(job); raise
            job.state=OutreachState.SENT; job.sent_at=self.now(); job.updated_at=job.sent_at; self.store.save(job); last=job.sent_at
    @staticmethod
    def _check_hours(now):
        if not time(8,0) <= now.time().replace(tzinfo=None) < time(20,0): raise OutreachLimitsExceeded("outreach is allowed 08:00-20:00 WIB")
