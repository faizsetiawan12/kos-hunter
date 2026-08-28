"""
Mamikos platform adapter.

Uses the internal garuda API reverse-engineered from the Mamikos web app.
Full API reference: docs/MAMIKOS_API.md
"""

import base64
import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

import requests
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

# ── Decryption constants (extracted from chunk/langTranslator.*.js) ──────────
_AES_KEY = b"39c852d0d0bc42ef83f7d3d708f42368"
_AES_IV  = b"5df5a10ebb035097"

# ── Bounding boxes [SW, NE] as (lng, lat) ────────────────────────────────────
AREAS: dict[str, dict] = {
    "kukel": {
        "label": "Kukel (Kukusan Kelurahan)",
        "sw": (106.815, -6.375),
        "ne": (106.830, -6.355),
    },
    "kutek": {
        "label": "Kutek (Kukusan Teknik)",
        "sw": (106.820, -6.370),
        "ne": (106.840, -6.350),
    },
    "ui_wide": {
        "label": "UI campus wide (Pocin, Barel, Kober)",
        "sw": (106.800, -6.400),
        "ne": (106.860, -6.330),
    },
}

CREDENTIALS_FILE = Path.home() / ".openclaw" / "kos-hunter" / "mamikos_session.json"

GENDER_PUTRA_CAMPUR = [0, 1]
GENDER_ALL          = [0, 1, 2]


@dataclass
class KosListing:
    platform:      str
    platform_id:   str
    title:         str
    url:           str
    price_monthly: int
    gender:        int        # 0=campur, 1=putra, 2=putri
    area_label:    str
    address:       str
    available:     bool
    fac_room_ids:  list[int]
    fac_share_ids: list[int]
    rating:        float | None
    review_count:  int
    contact:       str        # empty until get_contact() called
    raw:           dict = field(repr=False, default_factory=dict)

    @property
    def price_str(self) -> str:
        return f"Rp{self.price_monthly:,.0f}".replace(",", ".")


class PlatformAuthError(Exception):
    pass


class MamikosAdapter:
    """Mamikos internal garuda API adapter."""

    BASE_URL    = "https://mamikos.com"
    LIST_EP     = "/garuda/stories/list?v=2&with_thematic_badge=true"
    FILTERS_EP  = "/garuda/stories/filters"

    STATIC_HEADERS = {
        "Authorization": "GIT WEB:WEB",
        "X-GIT-Time":    "1406090202",
        "User-Agent":    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:154.0) Gecko/20100101 Firefox/154.0",
        "Accept-Language": "en-US,en;q=0.9",
        "Origin":        "https://mamikos.com",
        "Referer":       "https://mamikos.com/cari/ui/all/bulanan/0-15000000?rent=2",
    }

    @property
    def name(self) -> str:
        return "mamikos"

    def __init__(self) -> None:
        self._session = requests.Session()
        self._session.headers.update(self.STATIC_HEADERS)
        self._load_credentials()

    # ── Credentials ──────────────────────────────────────────────────────────

    def _load_credentials(self) -> None:
        if not CREDENTIALS_FILE.exists():
            raise PlatformAuthError(
                f"Mamikos credentials not found at {CREDENTIALS_FILE}.\n"
                "Capture session from browser DevTools and save to that path.\n"
                "See docs/MAMIKOS_API.md → Authentication."
            )
        creds = json.loads(CREDENTIALS_FILE.read_text())
        self._session.cookies.set("laravel_session", creds["laravel_session"], domain="mamikos.com")
        self._session.cookies.set("XSRF-TOKEN",      creds["xsrf_token"],      domain="mamikos.com")
        self._session.cookies.set("adsession",        creds.get("adsession", ""), domain="mamikos.com")
        self._session.headers["X-XSRF-TOKEN"] = creds["xsrf_token"]

    def _save_credentials(self, response: requests.Response) -> None:
        """Persist rotated XSRF/session cookies from a response."""
        new_xsrf    = response.cookies.get("XSRF-TOKEN")
        new_session = response.cookies.get("laravel_session")
        if not (new_xsrf and new_session):
            return
        creds = json.loads(CREDENTIALS_FILE.read_text()) if CREDENTIALS_FILE.exists() else {}
        creds["xsrf_token"]      = new_xsrf
        creds["laravel_session"] = new_session
        CREDENTIALS_FILE.parent.mkdir(parents=True, exist_ok=True)
        CREDENTIALS_FILE.write_text(json.dumps(creds, indent=2))
        self._session.cookies.set("XSRF-TOKEN",      new_xsrf,    domain="mamikos.com")
        self._session.cookies.set("laravel_session",  new_session, domain="mamikos.com")
        self._session.headers["X-XSRF-TOKEN"] = new_xsrf

    # ── Session health ────────────────────────────────────────────────────────

    def health_check(self) -> bool:
        try:
            r = self._session.get(
                f"{self.BASE_URL}{self.FILTERS_EP}",
                timeout=10,
            )
            return r.status_code == 200
        except requests.RequestException:
            return False

    def refresh_session(self) -> None:
        """Refresh cookies by hitting the search page (no login required)."""
        r = self._session.get(
            f"{self.BASE_URL}/cari/ui/all/bulanan/0-15000000",
            timeout=15,
        )
        if r.status_code != 200:
            raise PlatformAuthError(
                "Session refresh failed. Re-capture cookies from browser.\n"
                "See docs/MAMIKOS_API.md → Authentication."
            )
        self._save_credentials(r)

    # ── Decryption ────────────────────────────────────────────────────────────

    @staticmethod
    def _decrypt_rooms(encrypted_b64: str) -> list[dict]:
        raw = base64.b64decode(encrypted_b64)
        cipher = AES.new(_AES_KEY, AES.MODE_CBC, _AES_IV)
        decrypted = unpad(cipher.decrypt(raw), AES.block_size)
        return json.loads(decrypted.decode("utf-8"))

    # ── Search ────────────────────────────────────────────────────────────────

    def search(
        self,
        area:       str  = "kukel",
        price_max:  int  = 2_000_000,
        gender:     list | None = None,
        page_delay: float = 2.0,
    ) -> list[KosListing]:
        """
        Return all matching listings for the given area.
        Paginates automatically until has-more is False.
        """
        if area not in AREAS:
            raise ValueError(f"Unknown area '{area}'. Choose from: {list(AREAS)}")

        bbox   = AREAS[area]
        gender = gender if gender is not None else GENDER_PUTRA_CAMPUR

        results: list[KosListing] = []
        offset = 0

        while True:
            payload = {
                "filters": {
                    "gender":       gender,
                    "price_range":  [100_000, price_max],
                    "tag_ids":      [],
                    "rent_type":    2,
                    "property_type":"kost",
                    "random_seeds": 42,
                    "flash_sale":   False,
                    "goldplus":     [],
                    "kost_levels":  [],
                    "is_expand":    False,
                    "is_available": False,
                    "mamirooms":    False,
                },
                "sorting":          {"field": "price", "direction": "+"},
                "is_for_map":       False,
                "geocode_id":       None,
                "location":         [
                    list(bbox["sw"]),   # [sw_lng, sw_lat]
                    list(bbox["ne"]),   # [ne_lng, ne_lat]
                ],
                "point":            {},
                "include_promoted": False,
                "limit":            20,
                "offset":           offset,
            }

            r = self._session.post(
                f"{self.BASE_URL}{self.LIST_EP}",
                json=payload,
                headers={"Content-Type": "application/json", "Accept": "application/json"},
                timeout=30,
            )

            if r.status_code == 419:
                self.refresh_session()
                continue  # retry same page

            r.raise_for_status()
            self._save_credentials(r)

            data  = r.json()
            rooms_enc = data.get("rooms", "")
            if not isinstance(rooms_enc, str) or not rooms_enc:
                break

            rooms = self._decrypt_rooms(rooms_enc)
            for raw in rooms:
                listing = self._parse_room(raw)
                if listing:
                    results.append(listing)

            if not data.get("has-more"):
                break

            offset += 20
            time.sleep(page_delay)

        return results

    def _parse_room(self, raw: dict) -> KosListing | None:
        price_fmt = raw.get("price_title_format") or {}
        price_str = price_fmt.get("price", "0").replace(".", "").replace(",", "")
        try:
            price = int(price_str)
        except ValueError:
            return None

        return KosListing(
            platform      = self.name,
            platform_id   = str(raw.get("_id", "")),
            title         = raw.get("room-title") or raw.get("room_title", ""),
            url           = raw.get("share_url", ""),
            price_monthly = price,
            gender        = raw.get("gender", 0),
            area_label    = raw.get("area_label", ""),
            address       = raw.get("address", ""),
            available     = bool(raw.get("available_room", 0)),
            fac_room_ids  = raw.get("fac_room_ids") or [],
            fac_share_ids = raw.get("fac_share_ids") or [],
            rating        = raw.get("rating"),
            review_count  = raw.get("review_count", 0),
            contact       = "",
            raw           = raw,
        )

    # ── Contact retrieval ─────────────────────────────────────────────────────

    def get_contact(self, listing: KosListing) -> str:
        """
        Fetch the room detail page and extract the landlord phone number.
        Returns empty string if not found.
        """
        if not listing.url:
            return ""
        try:
            r = self._session.get(listing.url, timeout=15)
            r.raise_for_status()
            match = re.search(r"(08[0-9]{8,13})", r.text)
            return match.group(1) if match else ""
        except requests.RequestException:
            return ""
