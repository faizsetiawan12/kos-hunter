import io
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr

from kos_hunter.application import SearchFacade
from kos_hunter.domain import (
    ContactStatus,
    Gender,
    KosListing,
    SearchCriteria,
    TenantProfile,
    normalize_phone,
)
from kos_hunter.fakes import FakeListingSource
from kos_hunter.persistence import SQLitePersistenceAdapter


class ContactSource:
    def __init__(self, values):
        self.values = values
        self.calls = []

    def get_contact(self, listing):
        self.calls.append(listing.id)
        value = self.values[listing.id]
        if isinstance(value, Exception):
            raise value
        return value


class ContactEnrichmentTests(unittest.TestCase):
    def listing(self, ident, *, price=1_000_000, url=None, links=()):
        return KosListing(
            ident, ident, price, Gender.CAMPUR, "Kukel", source="mamikos",
            url=url or f"https://mamikos.test/{ident}", source_links=tuple(links),
        )

    def criteria(self):
        return SearchCriteria(2_000_000, TenantProfile(Gender.PUTRA), location="Kukel")

    def test_retrieves_contacts_only_for_shortlisted_candidates(self):
        discovered = [self.listing("short"), self.listing("over-budget", price=2_000_001)]
        source = ContactSource({"short": "081234567890", "over-budget": "081298765432"})
        shortlist = SearchFacade([FakeListingSource(discovered)]).search(self.criteria())

        contacts = SearchFacade([]).enrich_contacts(shortlist, source)

        self.assertEqual(source.calls, ["short"])
        self.assertIn("+6281234567890", contacts)

    def test_normalizes_indonesian_mobile_numbers_to_canonical_format(self):
        for value in ("081234567890", "6281234567890", "+6281234567890"):
            with self.subTest(value=value):
                self.assertEqual(normalize_phone(value), "+6281234567890")

    def test_same_normalized_phone_merges_links_and_platform_metadata(self):
        first = self.listing("a", url="https://mamikos.test/a", links=("https://source.test/a",))
        second = self.listing("b", url="https://mamikos.test/b", links=("https://source.test/b",))
        source = ContactSource({"a": "081234567890", "b": "+6281234567890"})
        shortlist = [
            # Scores are irrelevant to enrichment; both are already shortlisted.
            type("Ranked", (), {"listing": first})(),
            type("Ranked", (), {"listing": second})(),
        ]

        contacts = SearchFacade([]).enrich_contacts(shortlist, source)

        self.assertEqual(list(contacts), ["+6281234567890"])
        self.assertEqual(
            contacts["+6281234567890"].source_links,
            ("https://source.test/a", "https://mamikos.test/a",
             "https://source.test/b", "https://mamikos.test/b"),
        )

    def test_contact_outcomes_are_explicit(self):
        listings = [self.listing(x) for x in ("available", "missing", "malformed", "inaccessible")]
        source = ContactSource({
            "available": "081234567890", "missing": None,
            "malformed": "not-a-phone", "inaccessible": RuntimeError("403"),
        })
        ranked = [type("Ranked", (), {"listing": listing})() for listing in listings]

        contacts = SearchFacade([]).enrich_contacts(ranked, source)

        self.assertEqual(contacts["+6281234567890"].status, ContactStatus.AVAILABLE)
        self.assertEqual(contacts["listing:mamikos:missing"].status, ContactStatus.MISSING)
        self.assertEqual(contacts["listing:mamikos:malformed"].status, ContactStatus.MALFORMED)
        self.assertEqual(contacts["listing:mamikos:inaccessible"].status, ContactStatus.INACCESSIBLE)

    def test_phone_is_local_persistence_only_not_public_logs(self):
        with tempfile.NamedTemporaryFile() as f:
            db = SQLitePersistenceAdapter(f.name)
            listing = self.listing("private")
            ranked = type("Ranked", (), {"listing": listing, "score": 1, "reasons": ()})()
            source = ContactSource({"private": "081234567890"})
            stdout, stderr = io.StringIO(), io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                SearchFacade([], db).enrich_contacts([ranked], source)
            public_output = stdout.getvalue() + stderr.getvalue()
            self.assertNotIn("081234567890", public_output)
            self.assertNotIn("+6281234567890", public_output)
            with db._connect() as conn:
                self.assertEqual(conn.execute("select phone from contacts").fetchone()[0], "+6281234567890")


if __name__ == "__main__":
    unittest.main()
