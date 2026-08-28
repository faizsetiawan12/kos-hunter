import unittest
from unittest.mock import Mock, patch

from kos_hunter.domain import Gender, SearchCriteria, TenantProfile
from search.mamikos import (
    MamikosAdapter,
    MamikosDecryptionError,
    MamikosMalformedResponse,
    MamikosRateLimited,
    MamikosSessionExpired,
)


class Response:
    def __init__(self, status=200, data=None, text=""):
        self.status_code = status
        self._data = data
        self.text = text

    def json(self):
        if isinstance(self._data, Exception):
            raise self._data
        return self._data


class MamikosAdapterTests(unittest.TestCase):
    def setUp(self):
        self.session = Mock()
        self.adapter = MamikosAdapter(session=self.session, page_delay=0)
        self.criteria = SearchCriteria(2_000_000, TenantProfile(Gender.PUTRA))

    def test_payload_translates_gender_price_and_facilities(self):
        raw = {
            "_id": "room-1", "room-title": "Kost Kukel", "gender": 1,
            "price_title_format": {"price": "1.500.000"},
            "area_label": "Kukel", "fac_room_ids": [13, 1, 742],
            "fac_share_ids": [], "share_url": "https://mamikos.com/room-1",
        }
        listing = self.adapter._parse_room(raw)
        self.assertEqual(listing.id, "room-1")
        self.assertEqual(listing.price, 1_500_000)
        self.assertEqual(listing.gender, Gender.PUTRA)
        self.assertEqual(listing.amenities, frozenset({"AC", "private bathroom", "wifi"}))
        self.assertEqual(listing.url, "https://mamikos.com/room-1")

        raw["gender"] = 0
        self.assertEqual(self.adapter._parse_room(raw).gender, Gender.CAMPUR)
        raw["gender"] = 2
        self.assertEqual(self.adapter._parse_room(raw).gender, Gender.PUTRI)

    def test_search_handles_encrypted_room_pages_and_pagination(self):
        pages = [
            {"rooms": "encrypted-page-1", "has-more": True, "next-offset": 20},
            {"rooms": "encrypted-page-2", "has-more": False},
        ]
        self.session.post.side_effect = [Response(data=p) for p in pages]
        rooms = [
            {"_id": "a", "room_title": "A", "gender": 0, "price_title_format": {"price": 1000000}},
            {"_id": "b", "room_title": "B", "gender": 1, "price_title_format": {"price": 1200000}},
        ]
        with patch.object(self.adapter, "decrypt_rooms", side_effect=[[rooms[0]], [rooms[1]]]) as decrypt:
            result = self.adapter.search(self.criteria, page_delay=0)
        self.assertEqual([x.id for x in result], ["a", "b"])
        self.assertEqual(decrypt.call_args_list[0].args, ("encrypted-page-1",))
        self.assertEqual(self.session.post.call_args_list[1].kwargs["json"]["offset"], 20)

    def test_explicit_errors_for_session_rate_limit_and_malformed_response(self):
        for status, error in ((401, MamikosSessionExpired), (429, MamikosRateLimited)):
            self.session.post.return_value = Response(status=status)
            with self.subTest(status=status), self.assertRaises(error):
                self.adapter.search(self.criteria, page_delay=0)

        for data in ({}, {"rooms": [{"not": "encrypted"}]}):
            self.session.post.return_value = Response(data=data)
            with self.subTest(data=data), self.assertRaises(MamikosMalformedResponse):
                self.adapter.search(self.criteria, page_delay=0)

    def test_decryption_failure_is_exposed(self):
        self.session.post.return_value = Response(data={"rooms": "corrupt"})
        with patch.object(self.adapter, "decrypt_rooms", side_effect=MamikosDecryptionError("bad fixture")):
            with self.assertRaises(MamikosDecryptionError):
                self.adapter.search(self.criteria, page_delay=0)

    def test_detail_page_parses_landlord_phone(self):
        self.session.get.return_value = Response(text="Hubungi pemilik: 081234567890 untuk viewing")
        self.assertEqual(self.adapter.get_owner_phone("https://mamikos.com/detail"), "081234567890")


if __name__ == "__main__":
    unittest.main()
