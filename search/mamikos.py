"""Mamikos listing-source adapter; vendor details stop at this boundary."""
from __future__ import annotations
import base64, json, re, time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from kos_hunter.domain import Gender, KosListing, SearchCriteria

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None

_AES_KEY = b"39c852d0d0bc42ef83f7d3d708f42368"
_AES_IV = b"5df5a10ebb035097"
AREAS = {"kukel": ((106.815, -6.375), (106.830, -6.355)), "kutek": ((106.820, -6.370), (106.840, -6.350)), "ui_wide": ((106.800, -6.400), (106.860, -6.330))}
CREDENTIALS_FILE = Path.home() / ".openclaw" / "kos-hunter" / "mamikos_session.json"

class MamikosError(Exception): pass
class MamikosSessionExpired(MamikosError): pass
class MamikosRateLimited(MamikosError): pass
class MamikosMalformedResponse(MamikosError): pass
class MamikosDecryptionError(MamikosError): pass
PlatformAuthError = MamikosSessionExpired

FACILITIES = {1: "private bathroom", 8: "hot water", 13: "AC", 742: "wifi", 84: "electricity", 23: "parking"}
GENDERS = {0: Gender.CAMPUR, 1: Gender.PUTRA, 2: Gender.PUTRI}

class MamikosAdapter:
    BASE_URL = "https://mamikos.com"
    LIST_EP = "/garuda/stories/list?v=2&with_thematic_badge=true"
    FILTERS_EP = "/garuda/stories/filters"
    def __init__(self, session=None, credentials_file=CREDENTIALS_FILE, page_delay=2.0):
        self._session = session or (requests.Session() if requests else None)
        self.credentials_file, self.page_delay = Path(credentials_file), page_delay
        if session is None: self._load_credentials()
    @property
    def name(self): return "mamikos"
    def _load_credentials(self):
        if not self.credentials_file.exists(): raise MamikosSessionExpired("Mamikos session credentials are missing")
        try: c=json.loads(self.credentials_file.read_text()); token=c["xsrf_token"]; self._session.cookies.update({"laravel_session":c["laravel_session"],"XSRF-TOKEN":token}); self._session.headers.update({"X-XSRF-TOKEN":token,"Authorization":"GIT WEB:WEB","X-GIT-Time":"1406090202"})
        except (OSError, ValueError, KeyError) as e: raise MamikosSessionExpired("Invalid Mamikos credentials") from e
    @staticmethod
    def decrypt_rooms(value: str) -> list[dict]:
        try:
            from Crypto.Cipher import AES
            from Crypto.Util.Padding import unpad
            result=json.loads(unpad(AES.new(_AES_KEY,AES.MODE_CBC,_AES_IV).decrypt(base64.b64decode(value)), AES.block_size).decode())
            if not isinstance(result,list): raise ValueError
            return result
        except Exception as e: raise MamikosDecryptionError("Unable to decrypt Mamikos room list") from e
    _decrypt_rooms = decrypt_rooms
    def _request(self, offset, payload):
        try: r=self._session.post(self.BASE_URL+self.LIST_EP,json=payload,timeout=30)
        except Exception as e: raise MamikosError("Mamikos request failed") from e
        if r.status_code in (401,403,419): raise MamikosSessionExpired("Mamikos session expired")
        if r.status_code == 429: raise MamikosRateLimited("Mamikos rate limit exceeded")
        if r.status_code >= 400: raise MamikosError(f"Mamikos HTTP error {r.status_code}")
        try: data=r.json()
        except Exception as e: raise MamikosMalformedResponse("Mamikos returned invalid JSON") from e
        if not isinstance(data,dict) or not isinstance(data.get("rooms"),str): raise MamikosMalformedResponse("Mamikos response has no encrypted rooms")
        return data
    def search(self, criteria: SearchCriteria, area="kukel", gender=None, page_delay=None):
        if area not in AREAS: raise ValueError(f"Unknown area '{area}'")
        sw,ne=AREAS[area]; offset=0; out=[]; genders=gender or [0,1]
        while True:
            payload={"filters":{"gender":genders,"price_range":[0,criteria.max_price],"tag_ids":[],"rent_type":2,"property_type":"kost"},"sorting":{"field":"price","direction":"+"},"location":[list(sw),list(ne)],"geocode_id":None,"limit":20,"offset":offset}
            data=self._request(offset,payload)
            out.extend(x for raw in self.decrypt_rooms(data["rooms"]) if (x:=self._parse_room(raw)) is not None)
            if not data.get("has-more"): return out
            offset=int(data.get("next-offset",offset+20)); time.sleep(self.page_delay if page_delay is None else page_delay)
    def _parse_room(self, raw: dict) -> KosListing:
        if not isinstance(raw,dict) or "_id" not in raw: raise MamikosMalformedResponse("Malformed room object")
        p=(raw.get("price_title_format") or {}).get("price",0)
        try: price=int(str(p).replace(".","").replace(",",""))
        except ValueError as e: raise MamikosMalformedResponse("Malformed room price") from e
        ids=list(raw.get("fac_room_ids") or [])+list(raw.get("fac_share_ids") or [])
        return KosListing(str(raw["_id"]),raw.get("room-title",raw.get("room_title","")),price,GENDERS.get(raw.get("gender"),Gender.CAMPUR),raw.get("area_label",""),frozenset(FACILITIES[i] for i in ids if i in FACILITIES),self.name,raw.get("share_url",""))
    def get_owner_phone(self, url):
        r=self._session.get(url,timeout=15)
        if r.status_code==429: raise MamikosRateLimited("Mamikos rate limit exceeded")
        if r.status_code in (401,403,419): raise MamikosSessionExpired("Mamikos session expired")
        return (re.search(r"08[0-9]{8,13}",r.text) or [""])[0]
    def get_contact(self, listing): return self.get_owner_phone(listing.url) if listing.url else ""
    def health_check(self):
        try: return self._session.get(self.BASE_URL+self.FILTERS_EP,timeout=10).status_code==200
        except Exception: return False
    def refresh_session(self): raise MamikosSessionExpired("Refresh session by capturing browser cookies")
