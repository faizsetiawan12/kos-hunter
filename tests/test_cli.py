import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import cli
from kos_hunter.domain import Gender, KosListing, SearchCriteria, TenantProfile, rank_listing
from search.mamikos import AREAS, MamikosAdapter


class CliSearchTests(unittest.TestCase):
    def listing(self, ident, price=1_000_000, gender=Gender.CAMPUR, amenities=frozenset()):
        return KosListing(ident, ident, price, gender, "Kukel", amenities,
                          source="mamikos", url="https://example.test/" + ident)

    def test_search_uses_adapter_with_credentials_and_writes_ranked_facilities(self):
        adapter = Mock()
        adapter.search.return_value = [self.listing("a", amenities=frozenset({"AC", "wifi", "private bathroom", "hot water"}))]
        with tempfile.TemporaryDirectory() as d, patch.object(cli, "SHORTLIST_FILE", Path(d) / "shortlist.json"), \
             patch.object(cli, "MamikosAdapter", return_value=adapter):
            with patch.dict(os.environ, {"MAMIKOS_AUTH_TOKEN": "test-token", "MAMIKOS_DEVICE_ID": "device"}):
                args = Mock(area="kukel", price_max=2_000_000)
                self.assertEqual(cli.cmd_search(args), 0)
        criteria = adapter.search.call_args.args[0]
        self.assertEqual(criteria.max_price, 2_000_000)
        self.assertEqual(adapter.search.call_args.kwargs["area"], "kukel")

    def test_hard_filters_exclude_putri_and_over_budget(self):
        adapter = Mock()
        adapter.search.return_value = [self.listing("ok"), self.listing("putri", gender=Gender.PUTRI), self.listing("expensive", price=2_000_001)]
        with tempfile.TemporaryDirectory() as d, patch.object(cli, "SHORTLIST_FILE", Path(d) / "shortlist.json"), patch.object(cli, "MamikosAdapter", return_value=adapter):
            self.assertEqual(cli.cmd_search(Mock(area="kukel", price_max=2_000_000)), 0)
            saved = json.loads((Path(d) / "shortlist.json").read_text())
        self.assertEqual([item["id"] for item in saved], ["ok"])

    def test_failed_search_does_not_clobber_existing_shortlist(self):
        adapter = Mock()
        adapter.search.side_effect = RuntimeError("network down")
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "shortlist.json"
            original = [{"id": "existing", "rank": 1}]
            path.write_text(json.dumps(original))
            with patch.object(cli, "SHORTLIST_FILE", path), patch.object(cli, "MamikosAdapter", return_value=adapter):
                self.assertEqual(cli.cmd_search(Mock(area="kukel", price_max=2_000_000)), 1)
            self.assertEqual(json.loads(path.read_text()), original)

    def test_unknown_facilities_are_not_reported_as_missing(self):
        adapter = MamikosAdapter(session=Mock())
        raw = {"_id": "x", "room-title": "X", "gender": 1,
               "price_title_format": {"price": 100}, "fac_room_ids": [999999]}
        listing = adapter._parse_room(raw)
        self.assertEqual(listing.amenities, frozenset())


class KukelQueryTests(unittest.TestCase):
    def test_kukel_bounding_box_is_sent(self):
        session = Mock()
        session.post.return_value = Mock(status_code=200, json=lambda: {"rooms": "encrypted", "has-more": False})
        adapter = MamikosAdapter(session=session, page_delay=0)
        with patch.object(adapter, "decrypt_rooms", return_value=[]):
            adapter.search(SearchCriteria(2_000_000, TenantProfile(Gender.PUTRA)), area="kukel", page_delay=0)
        self.assertEqual(session.post.call_args.kwargs["json"]["location"], [list(AREAS["kukel"][0]), list(AREAS["kukel"][1])])

    def test_soft_ranking_rewards_requested_facilities(self):
        preferred = frozenset({"AC", "wifi", "private bathroom", "hot water"})
        full = rank_listing(self_listing("full", preferred), TenantProfile(Gender.PUTRA, preferred))
        sparse = rank_listing(self_listing("sparse", frozenset()), TenantProfile(Gender.PUTRA, preferred))
        self.assertGreater(full.score, sparse.score)
        self.assertEqual(full.score - sparse.score, 40)


def self_listing(ident, amenities):
    return KosListing(ident, ident, 1_000_000, Gender.CAMPUR, "Kukel", amenities, available=False)


if __name__ == "__main__":
    unittest.main()
