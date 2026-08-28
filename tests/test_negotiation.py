import unittest
from datetime import datetime, timezone

from kos_hunter.application import SearchFacade
from kos_hunter.domain import Gender, KosListing, SearchCriteria, TenantProfile
from kos_hunter.fakes import FakeListingSource, FakeMessagingAdapter, FakeClock
from kos_hunter.negotiation import (
    ApprovalDecision, ApprovalKind, MemoryApprovalStore, NegotiationService,
    NegotiationState,
)
from kos_hunter.outreach import OutreachService


class NegotiationTests(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock(datetime(2026, 8, 28, 10, 0, tzinfo=timezone.utc))
        self.approvals = MemoryApprovalStore()
        self.service = NegotiationService(self.approvals, self.clock)

    def test_follow_up_clarifies_all_required_terms(self):
        state = NegotiationState("c1", 1_800_000)
        reply = self.service.reply(state, "Masih tersedia")
        for term in ("tersedia", "fasilitas", "listrik", "air", "deposit", "parkir motor"):
            self.assertIn(term, reply.lower())
        self.assertEqual(state.followups, 1)

    def test_price_negotiation_respects_two_million_ceiling(self):
        state = NegotiationState("c1", 1_900_000, essential_facts=set(self.service.required_facts))
        reply = self.service.reply(state, "Harga pas")
        self.assertIn("didiskusikan", reply)
        self.assertLessEqual(state.price, 2_000_000)

    def test_unsafe_termination_conditions(self):
        cases = [
            (NegotiationState("a", 2_100_000), dict(price=2_100_000)),
            (NegotiationState("b", 1_500_000), dict(deposit_before_survey=True)),
            (NegotiationState("c", 1_500_000, followups=2), dict(vague=True)),
        ]
        for state, kwargs in cases:
            with self.subTest(state=state.conversation_id):
                self.assertIn("belum bisa cocok", self.service.end_if_unsafe(state, **kwargs))
                self.assertTrue(state.ended)

    def test_honestly_discloses_assistant_when_asked(self):
        state = NegotiationState("c1", 1_500_000)
        reply = self.service.reply(state, "Ini bot atau AI?")
        self.assertIn("asisten", reply.lower())
        self.assertIn("konfirmasi", reply.lower())

    def test_survey_booking_contract_and_payment_are_approval_requests(self):
        for kind in ApprovalKind:
            request = self.service.request_approval(kind.value, kind.value, "c1", f"{kind.value} request")
            self.assertEqual(request.kind, kind)
            self.assertEqual(request.decision, ApprovalDecision.PENDING)
        self.assertEqual(len(self.approvals.all()), 4)

    def test_approval_lifecycle_requires_explicit_decision_and_is_audited(self):
        request = self.service.request_approval("r1", "booking", "c1", "confirm room")
        self.assertFalse(self.service.can_commit(request.id))
        self.assertEqual(request.decision, ApprovalDecision.PENDING)
        approved = self.service.decide("r1", True, decided_by="KIM")
        self.assertTrue(self.service.can_commit("r1"))
        self.assertEqual(approved.decision, ApprovalDecision.APPROVED)
        self.assertEqual(approved.decided_by, "KIM")
        self.assertIn(("r1", "approved", "KIM"), self.approvals.audit_log)
        with self.assertRaises(ValueError):
            self.service.decide("r1", False)

    def test_full_acceptance_search_outreach_reply_negotiation_handoff(self):
        listing = KosListing("1", "Kos Kukel", 1_800_000, Gender.CAMPUR, "Kukel", url="https://example.test/1", available=True)
        criteria = SearchCriteria(2_000_000, TenantProfile(Gender.PUTRA), location="Kukel")
        shortlist = SearchFacade([FakeListingSource([listing])]).search(criteria)
        self.assertEqual([x.listing.id for x in shortlist], ["1"])

        messaging = FakeMessagingAdapter()
        outreach = OutreachService(messaging, clock=self.clock, tenant_name="KIM")
        candidate = type("Candidate", (), {"listing": listing, "phone": "+6281234567890"})()
        job = outreach.queue([candidate])[0]
        with self.assertRaises(Exception):
            outreach.send_approved([job.id])
        outreach.approve([job.id]); outreach.send_approved([job.id])
        self.assertEqual(len(messaging.messages), 1)

        state = NegotiationState("c1", listing.price, essential_facts=set(self.service.required_facts))
        self.assertIn("didiskusikan", self.service.reply(state, "Bisa dibicarakan"))
        handoff = self.service.request_approval("survey-1", "survey", "c1", "survey slot")
        self.assertEqual(handoff.decision, ApprovalDecision.PENDING)
        self.assertFalse(self.service.can_commit(handoff.id))


if __name__ == "__main__":
    unittest.main()
