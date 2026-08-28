import unittest
from datetime import datetime
from kos_hunter.outreach import *
from kos_hunter.domain import KosListing, Gender, RankedListing
from kos_hunter.fakes import FakeMessagingAdapter, FakeClock

class Candidate:
    def __init__(self, listing, phone): self.listing=listing; self.phone=phone

class OutreachTests(unittest.TestCase):
    def setUp(self):
        self.clock=FakeClock(datetime(2026,8,28,9,0)); self.msg=FakeMessagingAdapter()
        self.s=OutreachService(self.msg, clock=self.clock, tenant_name='KIM')
        self.l=KosListing('1','Kos A',1500000,Gender.CAMPUR,'Kukel')
    def test_queue_draft_requires_approval(self):
        job=self.s.queue([Candidate(self.l,'+6281234567890')])[0]
        self.assertEqual(job.state, OutreachState.PENDING); self.assertIn('masih tersedia',job.message)
        with self.assertRaises(ApprovalRequired): self.s.send_approved([job.id])
    def test_approved_sends_and_retry_is_idempotent(self):
        job=self.s.queue([Candidate(self.l,'+6281234567890')])[0]; self.s.approve([job.id]); self.s.send_approved([job.id])
        self.assertEqual(job.state, OutreachState.SENT); self.assertEqual(len(self.msg.messages),1)
        with self.assertRaises(ApprovalRequired): self.s.send_approved([job.id])
        self.assertEqual(len(self.msg.messages),1)
    def test_limits_hours_and_spacing(self):
        a=self.s.queue([Candidate(self.l,'+628111111111')])[0]; self.s.approve([a.id]); self.s.send_approved([a.id])
        b=self.s.queue([Candidate(KosListing('2','Kos B',100,Gender.CAMPUR,'Kukel'),'+628222222222')])[0]; self.s.approve([b.id])
        with self.assertRaises(OutreachLimitsExceeded): self.s.send_approved([b.id])
        self.clock.current=datetime(2026,8,28,9,1); self.assertRaises(OutreachLimitsExceeded, self.s.send_approved,[b.id])
        self.clock.current=datetime(2026,8,28,9,4); self.s.send_approved([b.id]); self.assertEqual(len(self.msg.messages),2)
    def test_outside_hours_rejected(self):
        self.clock.current=datetime(2026,8,28,20,0); j=self.s.queue([Candidate(self.l,'+628123456789')])[0]; self.s.approve([j.id])
        with self.assertRaises(OutreachLimitsExceeded): self.s.send_approved([j.id])
if __name__=='__main__': unittest.main()
