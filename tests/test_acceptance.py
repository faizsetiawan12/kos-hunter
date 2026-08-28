import unittest
from kos_hunter.application import SearchFacade
from kos_hunter.domain import Gender, KosListing, SearchCriteria, TenantProfile
from kos_hunter.fakes import FakeListingSource, FakePersistenceAdapter

class AcceptanceTests(unittest.TestCase):
    def test_filters_and_ranks(self):
        listings = [
            KosListing("1", "A", 1500000, Gender.CAMPUR, "Depok", frozenset({"AC", "wifi"})),
            KosListing("2", "B", 1600000, Gender.PUTRI, "Depok"),
            KosListing("3", "C", 2500000, Gender.CAMPUR, "Depok"),
        ]
        persistence = FakePersistenceAdapter()
        criteria = SearchCriteria(2000000, TenantProfile(Gender.PUTRA, frozenset({"AC", "wifi"})))
        result = SearchFacade([FakeListingSource(listings)], persistence).search(criteria)
        self.assertEqual([x.listing.id for x in result], ["1"])
        self.assertGreater(result[0].score, 0)
        self.assertTrue(result[0].reasons)
        self.assertEqual(len(persistence.shortlists), 1)

if __name__ == "__main__": unittest.main()
