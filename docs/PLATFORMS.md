# Platform Adapters

kos-hunter is built against a **platform adapter interface** — a standard contract every kos data source implements. Adding a new platform = writing one adapter class. The agent layer never changes.

---

## The contract

Every adapter must implement these five methods:

```python
class KosPlatformAdapter:

    def search(self, spec: SearchSpec) -> list[KosListing]:
        """
        Return all listings matching spec from this platform.
        Must handle pagination internally.
        Must respect rate limits (add delays between pages).
        """
        raise NotImplementedError

    def get_contact(self, listing: KosListing) -> str:
        """
        Return the landlord's contact (phone/WA number) for a listing.
        May require a second HTTP request (e.g. detail page fetch).
        Return empty string if unavailable.
        """
        raise NotImplementedError

    def health_check(self) -> bool:
        """
        Return True if the platform is reachable and session is valid.
        Called before every search run.
        """
        raise NotImplementedError

    def refresh_session(self) -> None:
        """
        Refresh auth tokens/cookies. Called automatically when health_check fails.
        Raises PlatformAuthError if refresh is impossible (manual re-login needed).
        """
        raise NotImplementedError

    @property
    def name(self) -> str:
        """Human-readable platform name, e.g. 'Mamikos'."""
        raise NotImplementedError
```

---

## Shared data types

```python
from dataclasses import dataclass, field

@dataclass
class SearchSpec:
    # Area — bounding box [SW, NE] as [lng, lat] pairs
    bbox_sw: tuple[float, float]          # (lng, lat)
    bbox_ne: tuple[float, float]          # (lng, lat)
    # Hard filters
    price_max:  int   = 2_000_000        # Rupiah/month
    rent_type:  str   = "bulanan"
    gender:     list  = field(default_factory=lambda: [0, 1, 2])  # 0=campur,1=putra,2=putri
    # Soft preferences (used for ranking, not rejection)
    prefer_ac:           bool = True
    prefer_private_bath: bool = True
    prefer_hot_shower:   bool = True
    prefer_wifi:         bool = True
    prefer_motor_parking:bool = False


@dataclass
class KosListing:
    platform:       str           # adapter name, e.g. "mamikos"
    platform_id:    str           # platform's internal ID
    title:          str
    url:            str           # canonical detail page URL
    price_monthly:  int           # Rupiah
    gender:         int           # 0/1/2
    area_label:     str
    address:        str
    available:      bool
    fac_room_ids:   list[int]     # platform-specific facility IDs (see adapter docs)
    fac_share_ids:  list[int]
    rating:         float | None
    review_count:   int
    contact:        str           # phone/WA, may be empty until get_contact() called
    raw:            dict          # full platform response, for debugging
```

---

## Implemented adapters

### `MamikosAdapter`

See [`MAMIKOS_API.md`](MAMIKOS_API.md) for the full API reference.

**Session management:** Mamikos uses rotating Laravel session cookies + XSRF tokens. The adapter stores them in a credentials file and refreshes automatically on 419 responses.

**Credentials file:** `~/.openclaw/kos-hunter/mamikos_session.json`
```json
{
  "laravel_session": "...",
  "xsrf_token":      "...",
  "adsession":       "...",
  "captured_at":     "2026-08-28T07:59:40Z"
}
```

Manual refresh needed when: `PlatformAuthError` is raised → open Mamikos in browser → DevTools → copy the four cookie/header values → update the credentials file.

**Bounding boxes for kos-hunter:**

```python
# Kukel (primary)
KUKEL_BBOX = {
    "sw": (106.815, -6.375),
    "ne": (106.830, -6.355),
}

# Wider UI campus fallback (Kutel, Pocin, Barel)
UI_AREA_BBOX = {
    "sw": (106.800, -6.400),
    "ne": (106.860, -6.330),
}
```

**Facility ID mapping (Mamikos-specific):**

| fac_room_id | Meaning |
|---|---|
| 1 | Kamar mandi dalam |
| 8 | Air panas |
| 13 | AC |
| 742 | Wifi |
| 84 | Listrik termasuk |

| fac_share_id | Meaning |
|---|---|
| 15 | WiFi (shared) |
| 23 | Parkir motor |
| 22 | Parkir mobil |

---

## Planned adapters

These platforms are candidates for future adapters. Each needs its own auth/session pattern.

### `SewaKostAdapter`
- Public listing pages (server-rendered, no login needed for list)
- Detail pages include phone directly in HTML
- No known internal API; parse HTML
- Rate limit: unknown; use 5s delay between pages

### `NinetyNineAdapter` (99.co)
- Suspected GraphQL API (inspect DevTools on `99.co/id/sewa/kost`)
- Listings include full address and price
- Phone requires login

### `OLXAdapter`
- Heavy anti-bot (Cloudflare). Lowest priority.
- Only try if other platforms yield insufficient Kukel coverage.

### `ManualFeedAdapter`
- Not a real platform — accepts screenshots and URLs pasted by the user
- Parse with vision model or structured prompt
- Zero ToS risk; zero automation fragility
- Use as fallback when platform adapters fail or coverage is thin

---

## Adding a new adapter

1. Create `adapters/<platform_name>.py` implementing all five methods above.
2. Document its session management and credential format in `docs/<PLATFORM_NAME>_API.md`.
3. Register it in `adapters/__init__.py`:
   ```python
   ADAPTERS = {
       "mamikos":  MamikosAdapter,
       "sewakost": SewaKostAdapter,   # add here
   }
   ```
4. Add its bounding-box constants to `config/areas.py`.
5. Test with `python -m kos_hunter.cli search --platform <name> --area kukel --dry-run`.

The agent selects adapters via config — no code change needed to switch platforms.

---

## Deduplication

When multiple adapters are active, the same physical kos may appear on multiple platforms under different IDs. Deduplicate by:
1. Exact title + area_label match (cheap, misses variants)
2. Normalized address match (strip Jl./Jalan, lowercase, remove spaces)
3. Phone number match after `get_contact()` (definitive — same phone = same landlord)

The agent contacts each physical kos once, regardless of how many platforms list it.
