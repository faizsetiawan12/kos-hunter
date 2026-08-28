import threading
import unittest
from unittest.mock import Mock

from kos_hunter.domain import Gender, KosListing, SearchCriteria, TenantProfile, RankedListing
from kos_hunter.fakes import FakeListingSource, FakeNotificationAdapter
from kos_hunter.application import SearchFacade
from kos_hunter.openclaw import OpenClawSearchEntryPoint, SearchAlreadyRunning


class OpenClawEntryTests(unittest.TestCase):
    def criteria(self):
        return SearchCriteria(2_000_000, TenantProfile(Gender.PUTRA), location="Kukel")

    def test_registered_entry_point_uses_application_facade_and_reports_progress_and_shortlist(self):
        listing = KosListing("1", "Kos Mawar", 1_200_000, Gender.CAMPUR, "Kukel",
                             frozenset({"wifi"}), source="mamikos", url="https://example.test/1", available=True)
        notifications = FakeNotificationAdapter()
        facade = Mock(spec=SearchFacade)
        result = RankedListing(listing, 15, ("Tersedia", "Memiliki wifi"))
        facade.run.return_value = [result]
        entry = OpenClawSearchEntryPoint(facade, notifications)

        self.assertEqual(entry.start_search(self.criteria()), [result])
        facade.run.assert_called_once_with(self.criteria())
        self.assertIn("dimulai", notifications.notifications[0])
        self.assertIn("selesai", notifications.notifications[1])
        self.assertIn("Kos Mawar", notifications.notifications[2])
        self.assertIn("Tersedia, Memiliki wifi", notifications.notifications[2])
        self.assertIn("https://example.test/1", notifications.notifications[2])

    def test_facade_is_shared_use_case_and_filters_and_ranks_fake_listings(self):
        source = FakeListingSource([
            KosListing("exp", "Mahal", 2_000_001, Gender.CAMPUR, "Kukel"),
            KosListing("putri", "Putri", 1_000_000, Gender.PUTRI, "Kukel"),
            KosListing("ok", "Tersedia", 1_000_000, Gender.CAMPUR, "Kukel", available=True),
        ])
        entry = OpenClawSearchEntryPoint(SearchFacade([source]), FakeNotificationAdapter())
        results = entry.search(self.criteria())
        self.assertEqual([r.listing.id for r in results], ["ok"])

    def test_platform_failure_is_actionable_and_releases_guard(self):
        notifications = FakeNotificationAdapter()
        facade = Mock(spec=SearchFacade)
        facade.run.side_effect = [RuntimeError("rate limit"), []]
        entry = OpenClawSearchEntryPoint(facade, notifications)
        with self.assertRaisesRegex(RuntimeError, "rate limit"):
            entry.start_search(self.criteria())
        self.assertIn("gagal", notifications.notifications[1])
        self.assertIn("koneksi/platform", notifications.notifications[1])
        self.assertEqual(entry.start_search(self.criteria()), [])

    def test_repeated_requests_cannot_run_concurrently(self):
        started = threading.Event(); release = threading.Event()
        facade = Mock(spec=SearchFacade)
        def blocked(_):
            started.set(); release.wait(2); return []
        facade.run.side_effect = blocked
        notifications = FakeNotificationAdapter()
        entry = OpenClawSearchEntryPoint(facade, notifications)
        first = threading.Thread(target=entry.start_search, args=(self.criteria(),))
        first.start(); self.assertTrue(started.wait(1))
        with self.assertRaises(SearchAlreadyRunning):
            entry.start_search(self.criteria())
        release.set(); first.join(2)
        self.assertEqual(facade.run.call_count, 1)
        self.assertTrue(any("sedang berjalan" in n for n in notifications.notifications))

if __name__ == "__main__":
    unittest.main()
