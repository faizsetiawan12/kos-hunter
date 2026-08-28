import tempfile, unittest
from kos_hunter.application import SearchFacade
from kos_hunter.domain import Gender, KosListing, SearchCriteria, TenantProfile
from kos_hunter.fakes import FakeListingSource
from kos_hunter.persistence import SQLitePersistenceAdapter

class PersistenceTests(unittest.TestCase):
    def test_search_survives_restart_without_source(self):
        with tempfile.NamedTemporaryFile() as f:
            criteria = SearchCriteria(2_000_000, TenantProfile(Gender.PUTRA, frozenset({'wifi'})), location='Depok')
            listing = KosListing('abc','Kos A',1_500_000,Gender.CAMPUR,'Depok',frozenset({'wifi'}),source='mamikos',url='u')
            db = SQLitePersistenceAdapter(f.name)
            result = SearchFacade([FakeListingSource([listing])], db, 'kim').search(criteria)
            run = db.latest_run('kim')
            restarted = SQLitePersistenceAdapter(f.name)
            self.assertEqual(restarted.load_shortlist(run), result)
            self.assertEqual(SearchFacade([], restarted).run(criteria), [])

    def test_same_platform_listing_is_idempotent(self):
        with tempfile.NamedTemporaryFile() as f:
            db = SQLitePersistenceAdapter(f.name)
            listing = KosListing('same','Kos',100,Gender.CAMPUR,source='mamikos')
            criteria = SearchCriteria(1000,TenantProfile(Gender.PUTRA))
            facade = SearchFacade([FakeListingSource([listing])],db)
            facade.search(criteria); facade.search(criteria)
            with db._connect() as conn:
                self.assertEqual(conn.execute('select count(*) from listings').fetchone()[0], 1)

if __name__ == '__main__': unittest.main()
