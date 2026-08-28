# Mamikos Internal API Reference

> **Status:** Reverse-engineered from browser DevTools (August 2026).  
> **Stability:** Private/unofficial. Session tokens rotate; encryption keys and endpoint paths may change on app deploy.  
> **Access note:** Mamikos `robots.txt` allowed its public pages when checked in August 2026. That does not grant permission to use private endpoints or override platform terms. Review current terms before production or commercial use.

---

## Authentication

Every request needs four auth artifacts — all captured together from one browser session.

| Artifact | Where it lives | How to refresh |
|---|---|---|
| `laravel_session` cookie | Cookie jar | Re-login or revisit mamikos.com; expires on logout |
| `XSRF-TOKEN` cookie | Cookie jar | Rotates per request (server sets new value in `set-cookie`) |
| `X-XSRF-TOKEN` header | Request header | Must match current `XSRF-TOKEN` cookie value |
| `Authorization: GIT WEB:WEB` | Request header | Static string — does not rotate |
| `X-GIT-Time: 1406090202` | Request header | Static integer — does not rotate |

**Session refresh flow:**
1. GET `https://mamikos.com/cari/ui/all/bulanan/0-15000000` with existing cookies
2. Read new `set-cookie: XSRF-TOKEN=...` and `set-cookie: laravel_session=...` from response headers
3. Use new values for all subsequent requests

Rate limit: `x-ratelimit-limit: 60` requests/minute. Stay well under — target ≤10 req/min.

---

## Endpoint 1 — Filter Vocabulary

Fetches all valid filter IDs (facility tags, rules, rent types). Call once per session to build your filter map.

```
GET https://mamikos.com/garuda/stories/filters
```

**Required headers:** all auth headers above + `Referer: https://mamikos.com/cari/ui/all/bulanan/0-15000000`

**Response (HTTP 200, JSON):**
```json
{
  "status": true,
  "fac_room": [
    {"fac_id": 1,   "fac_name": "K. Mandi Dalam"},
    {"fac_id": 8,   "fac_name": "Air panas"},
    {"fac_id": 13,  "fac_name": "AC"},
    {"fac_id": 14,  "fac_name": "Meja"},
    {"fac_id": 742, "fac_name": "Wifi"},
    {"fac_id": 84,  "fac_name": "Termasuk listrik"},
    ...
  ],
  "fac_share": [
    {"fac_id": 15, "fac_name": "WiFi"},
    {"fac_id": 22, "fac_name": "Parkir Mobil"},
    {"fac_id": 23, "fac_name": "Parkir Motor"},
    ...
  ],
  "kos_rule": [...],
  "rent_type": [
    {"id": 1, "rent_name": "Mingguan"},
    {"id": 2, "rent_name": "Bulanan"},
    {"id": 3, "rent_name": "Tahunan"},
    ...
  ]
}
```

**Key facility IDs for Ngekos AI:**

| fac_id | Meaning |
|---|---|
| 1 | Kamar mandi dalam |
| 8 | Air panas (hot shower) |
| 13 | AC |
| 742 | Wifi (in-room) |
| 84 | Listrik termasuk |
| 23 | Parkir motor (shared) |

**Gender values (used in room list):** `0` = campur, `1` = putra, `2` = putri

---

## Endpoint 2 — Room List

The main search endpoint. Returns paginated, AES-encrypted room data.

```
POST https://mamikos.com/garuda/stories/list?v=2&with_thematic_badge=true
Content-Type: application/json
```

**Required headers:** all auth headers + `Origin: https://mamikos.com`

### Request payload

```json
{
  "filters": {
    "gender":       [0, 1, 2],
    "price_range":  [1000000, 2000000],
    "tag_ids":      [1, 8, 13, 742],
    "rent_type":    2,
    "property_type":"kost",
    "random_seeds": 42,
    "flash_sale":   false,
    "goldplus":     [],
    "kost_levels":  [],
    "is_expand":    false,
    "is_available": false,
    "mamirooms":    false
  },
  "sorting":         {"field": "price", "direction": "-"},
  "is_for_map":      false,
  "geocode_id":      null,
  "location":        [[106.815, -6.375], [106.830, -6.355]],
  "point":           {},
  "include_promoted":false,
  "limit":           20,
  "offset":          0
}
```

### Field reference

**`filters.gender`** — array of accepted gender codes. `[0,1,2]` = all. For putra only: `[0,1]`. For putri only: `[0,2]`.

**`filters.price_range`** — `[min_rupiah, max_rupiah]`. Use `[1000000, 2000000]` for the budget.

**`filters.tag_ids`** — facility IDs from Endpoint 1. Empty array `[]` = no facility filter (returns everything, filter client-side). Passing IDs server-filters — but only returns rooms with ALL specified tags; use `[]` and filter client-side for more results.

**`filters.rent_type`** — `2` = bulanan.

**`filters.random_seeds`** — integer 0–1000, random per request. Affects ranking tie-breaking, not correctness.

**`location`** — bounding box as `[[sw_lng, sw_lat], [ne_lng, ne_lat]]`. **Order is [longitude, latitude] — not [lat, lng].** This is the primary area scoping mechanism. `geocode_id: null` is correct for bbox searches.

**Kukel bounding box** (Kukusan Kelurahan, Pintu Kukel / Jl. Palakali area):
```
SW: [106.815, -6.375]
NE: [106.830, -6.355]
→ "location": [[106.815, -6.375], [106.830, -6.355]]
```

**Wider UI campus area** (includes Kutek, Pocin, Barel fallback):
```
SW: [106.800, -6.400]
NE: [106.860, -6.330]
→ "location": [[106.800, -6.400], [106.860, -6.330]]
```

**`sorting`** — `{"field":"price","direction":"-"}` = most expensive first. Use `"direction":"+"` for cheapest first (recommended).

**`limit`** / **`offset`** — pagination. Max 20 per page. Increment `offset` by 20 each page. Stop when `has-more: false`.

### Response

```json
{
  "status":    true,
  "total":     280,
  "has-more":  true,
  "next-offset": 20,
  "source":    "es",
  "rooms":     "<AES-encrypted-base64-string>",
  "room_quota": 240
}
```

`rooms` is an **AES-256-CBC encrypted, base64-encoded** JSON array. Decrypt before use — see section below.

### Decrypted room object (key fields)

```json
{
  "_id":               60555742,
  "room-title":        "Kost Kukusan Ahmad Dahlan Tipe B",
  "share_url":         "https://mamikos.com/room/kost-...-beji-depok-1",
  "area_label":        "Beji, Depok, Depok",
  "subdistrict":       "Beji",
  "address":           "Jl. ...",
  "gender":            1,
  "available_room":    3,
  "price_title_format":{"currency_symbol":"Rp","price":"1.655.000","rent_type_unit":"bulan"},
  "fac_room_ids":      [1, 13, 742],
  "fac_share_ids":     [15, 23],
  "rating":            4.8,
  "review_count":      12,
  "min_month":         1,
  "is_booking":        true,
  "unique_code":       "Z31V2HR4",
  "owner_phone":       "",
  "owner_phone_array": []
}
```

`owner_phone` is **always empty** in the list response — withheld to prevent mass harvesting. Retrieve it via Endpoint 3.

---

## Decryption

The `rooms` field is encrypted with a **static key and IV** embedded in Mamikos's JS bundle (`chunk/langTranslator.*.js` → imports `./aes.*.js`).

**Algorithm:** AES-256-CBC, PKCS7 padding  
**Key (UTF-8 string → 32 bytes):** `39c852d0d0bc42ef83f7d3d708f42368`  
**IV  (UTF-8 string → 16 bytes):** `5df5a10ebb035097`

### Python decryption

```python
import base64
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
import json

KEY = b"39c852d0d0bc42ef83f7d3d708f42368"
IV  = b"5df5a10ebb035097"

def decrypt_rooms(encrypted_b64: str) -> list[dict]:
    raw = base64.b64decode(encrypted_b64)
    cipher = AES.new(KEY, AES.MODE_CBC, IV)
    decrypted = unpad(cipher.decrypt(raw), AES.block_size)
    return json.loads(decrypted.decode("utf-8"))
```

### Shell (openssl) — no Python deps needed

```bash
KEY_HEX=$(printf '%s' "39c852d0d0bc42ef83f7d3d708f42368" | xxd -p | tr -d '\n')
IV_HEX=$(printf '%s'  "5df5a10ebb035097"                  | xxd -p | tr -d '\n')

echo "$ROOMS_B64" | base64 -d > /tmp/rooms.bin
openssl enc -d -aes-256-cbc -K "$KEY_HEX" -iv "$IV_HEX" \
  -in /tmp/rooms.bin -out /tmp/rooms.json
```

> **Brittle flag:** If Mamikos redeploys the JS bundle, the key/IV may change. If decryption fails (bad padding), re-extract: fetch the search page → find `<script src="...langTranslator.*.js">` → fetch that chunk → read `aes.*.js` import → decode the two base64 constants.

---

## Endpoint 3 — Room Detail (Phone Retrieval)

The landlord's phone number is embedded in the room's public HTML detail page. No additional auth required beyond the session cookie.

```
GET https://mamikos.com/room/<slug>
```

Where `<slug>` is the path component of `share_url` from the room object.

**Extract phone with Python:**

```python
import re, requests

def get_owner_phone(share_url: str, session: requests.Session) -> str:
    html = session.get(share_url).text
    match = re.search(r'(08[0-9]{8,13})', html)
    return match.group(1) if match else ""
```

**Notes:**
- The phone appears as a plain Indonesian mobile number: `08xx-xxxx-xxxx` or `08xxxxxxxxxx`.
- One GET per room. Respect rate limits — add a 3–5 second delay between calls.
- Some landlords list WhatsApp numbers; some list voice-only numbers. The agent should send WhatsApp first and fall back to SMS/voice.

---

## Pagination pattern

```python
offset = 0
all_rooms = []

while True:
    payload["offset"] = offset
    response = post_room_list(payload)
    rooms = decrypt_rooms(response["rooms"])
    all_rooms.extend(rooms)
    if not response.get("has-more"):
        break
    offset += 20
    time.sleep(2)  # polite delay
```

Total rooms available: check `response["total"]`. For Kukel bbox with budget ≤2jt: ~280 rooms as of Aug 2026.

---

## Known failure modes

| Symptom | Cause | Fix |
|---|---|---|
| HTTP 419 / CSRF error | `XSRF-TOKEN` expired | Refresh session (Endpoint 0 flow above) |
| HTTP 500 | Wrong payload shape | Check `location` is `[[lng,lat],[lng,lat]]` not `[[lat,lng],...]` |
| Decryption `bad padding` | Key/IV changed on redeploy | Re-extract from new JS bundle |
| `total: 0` with geocode_id set | Wrong geocode_id format | Use `geocode_id: null` with bbox `location` instead |
| `total: 1`, room in wrong city | Single `location` point used | Must pass two-pair bbox, not one point |
| `owner_phone` empty | Always empty in list response | Fetch detail page (Endpoint 3) |
