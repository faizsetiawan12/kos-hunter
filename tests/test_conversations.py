import unittest
from datetime import datetime, timezone, timedelta

from kos_hunter.conversations import (
    ConversationOutcome,
    InboundMessage,
    ConversationService,
    MemoryConversationStore,
)
from kos_hunter.domain import Gender, KosListing


class NotificationSpy:
    def __init__(self):
        self.messages = []

    def notify(self, message):
        self.messages.append(message)


class MessagingSpy:
    def __init__(self):
        self.sent = []

    def send(self, recipient, text):
        self.sent.append((recipient, text))


class FixedClock:
    def __init__(self, value):
        self.value = value

    def now(self):
        return self.value


class ConversationTests(unittest.TestCase):
    def setUp(self):
        self.listing = KosListing(
            id="listing-9", name="Kos Kukel AC", price=1_750_000,
            gender=Gender.CAMPUR, url="https://mamikos.com/kos/kukel-9",
        )
        self.sent_at = datetime(2026, 8, 25, 10, 0, tzinfo=timezone(timedelta(hours=7)))
        self.store = MemoryConversationStore()
        self.notice = NotificationSpy()
        self.service = ConversationService(self.store, self.notice, FixedClock(self.sent_at))
        self.conversation = self.service.start("conversation-9", "candidate-9", self.listing, "+628123456789", self.sent_at)

    def test_inbound_reply_correlates_candidate_conversation_and_outbound_history(self):
        self.conversation.outbound.append("Apakah kamar masih tersedia?")
        received = self.service.record_inbound(InboundMessage(
            "+628123456789", "Masih tersedia, silakan survey.", self.sent_at + timedelta(hours=2)))

        self.assertIs(received, self.store.get("conversation-9"))
        self.assertEqual(received.candidate_id, "candidate-9")
        self.assertEqual(received.id, "conversation-9")
        self.assertEqual(received.outbound, ["sent", "Apakah kamar masih tersedia?"])
        self.assertEqual(received.inbound, ["Masih tersedia, silakan survey."])
        self.assertEqual(received.outcome, ConversationOutcome.REPLIED)

    def test_reply_notification_contains_listing_details_and_context(self):
        self.service.record_inbound(InboundMessage(
            "+628123456789", "Ada AC dan wifi, Pak.", self.sent_at + timedelta(hours=1)))
        message = self.notice.messages[0]
        self.assertIn("Kos Kukel AC", message)
        self.assertIn("Rp1,750,000/bulan", message)
        self.assertIn("https://mamikos.com/kos/kukel-9", message)
        self.assertIn("Percakapan conversation-9", message)
        self.assertIn("Ada AC dan wifi", message)

    def test_verified_chat_facts_do_not_mutate_raw_listing(self):
        self.service.add_verified_fact("conversation-9", "availability", "tersedia")
        self.service.add_verified_fact("conversation-9", "AC", "verified")
        self.assertIsNone(self.listing.available)
        self.assertEqual(self.listing.amenities, frozenset())
        self.assertEqual([f.key for f in self.store.get("conversation-9").facts], ["availability", "AC"])

    def test_followup_requires_48_hours_and_business_hours_wib(self):
        for at in (
            self.sent_at + timedelta(hours=47, minutes=59),
            datetime(2026, 8, 27, 7, 59, tzinfo=timezone(timedelta(hours=7))),
            datetime(2026, 8, 27, 20, 0, tzinfo=timezone(timedelta(hours=7))),
        ):
            self.assertFalse(self.service.follow_up_eligible("conversation-9", at))
        eligible_at = datetime(2026, 8, 27, 10, 0, tzinfo=timezone(timedelta(hours=7)))
        self.assertTrue(self.service.follow_up_eligible("conversation-9", eligible_at))

    def test_at_most_one_followup_is_enforced(self):
        messaging = MessagingSpy()
        at = datetime(2026, 8, 27, 10, 0, tzinfo=timezone(timedelta(hours=7)))
        self.service.send_follow_up("conversation-9", messaging, at)
        self.assertEqual(len(messaging.sent), 1)
        with self.assertRaises(ValueError):
            self.service.send_follow_up("conversation-9", messaging, at + timedelta(days=2))
        self.assertEqual(len(messaging.sent), 1)

    def test_all_conversation_outcomes_are_persisted(self):
        for outcome in ConversationOutcome:
            self.service.mark_outcome("conversation-9", outcome)
            self.assertEqual(self.store.get("conversation-9").outcome, outcome)


if __name__ == "__main__":
    unittest.main()
