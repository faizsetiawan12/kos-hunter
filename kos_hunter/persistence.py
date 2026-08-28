"""SQLite persistence adapter for durable local search runs."""
from __future__ import annotations
import json, sqlite3
from dataclasses import asdict
from datetime import datetime, timezone
from .domain import Gender, KosListing, RankedListing, SearchCriteria, TenantProfile

class SQLitePersistenceAdapter:
    def __init__(self, database: str = "kos_hunter.sqlite3"):
        self.database = database
        self._init()

    def _connect(self):
        return sqlite3.connect(self.database)

    def _init(self):
        with self._connect() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS search_runs (id INTEGER PRIMARY KEY AUTOINCREMENT, owner_id TEXT NOT NULL, created_at TEXT NOT NULL, profile TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS listings (id INTEGER PRIMARY KEY AUTOINCREMENT, platform TEXT NOT NULL, platform_id TEXT NOT NULL, data TEXT NOT NULL, UNIQUE(platform, platform_id));
            CREATE TABLE IF NOT EXISTS candidates (run_id INTEGER NOT NULL REFERENCES search_runs(id), listing_id INTEGER NOT NULL REFERENCES listings(id), eligible INTEGER NOT NULL, score INTEGER NOT NULL, reasons TEXT NOT NULL, candidate_order INTEGER NOT NULL, PRIMARY KEY(run_id, listing_id));
            """)

    def start_search(self, owner_id: str, criteria: SearchCriteria) -> int:
        profile = {"max_price": criteria.max_price, "tenant_gender": criteria.tenant.gender.value,
                   "preferred_amenities": sorted(criteria.tenant.preferred_amenities), "location": criteria.location, "limit": criteria.limit}
        with self._connect() as db:
            cur = db.execute("INSERT INTO search_runs(owner_id,created_at,profile) VALUES(?,?,?)", (owner_id, datetime.now(timezone.utc).isoformat(), json.dumps(profile)))
            return int(cur.lastrowid)

    def save_search_run(self, run_id: int, listings, shortlist) -> None:
        shortlist = list(shortlist)
        with self._connect() as db:
            for order, ranked in enumerate(shortlist):
                listing = ranked.listing
                platform = listing.source or "unknown"
                db.execute("INSERT INTO listings(platform,platform_id,data) VALUES(?,?,?) ON CONFLICT(platform,platform_id) DO UPDATE SET data=excluded.data", (platform, listing.id, json.dumps(self._listing_data(listing))))
                lid = db.execute("SELECT id FROM listings WHERE platform=? AND platform_id=?", (platform, listing.id)).fetchone()[0]
                db.execute("INSERT INTO candidates(run_id,listing_id,eligible,score,reasons,candidate_order) VALUES(?,?,?,?,?,?) ON CONFLICT(run_id,listing_id) DO UPDATE SET eligible=excluded.eligible,score=excluded.score,reasons=excluded.reasons,candidate_order=excluded.candidate_order", (run_id,lid,1,ranked.score,json.dumps(ranked.reasons),order))

    def save_shortlist(self, shortlist):
        # Compatibility with the original persistence port; create an owner-local run.
        criteria = SearchCriteria(0, TenantProfile(Gender.CAMPUR))
        self.save_search_run(self.start_search("local", criteria), [], shortlist)

    def load_shortlist(self, run_id: int) -> list[RankedListing]:
        with self._connect() as db:
            rows = db.execute("SELECT l.data,c.score,c.reasons FROM candidates c JOIN listings l ON l.id=c.listing_id WHERE c.run_id=? AND c.eligible=1 ORDER BY c.candidate_order", (run_id,)).fetchall()
        return [RankedListing(self._listing(json.loads(data)), score, tuple(json.loads(reasons))) for data,score,reasons in rows]

    def latest_run(self, owner_id: str = "local"):
        with self._connect() as db:
            row = db.execute("SELECT id FROM search_runs WHERE owner_id=? ORDER BY id DESC LIMIT 1", (owner_id,)).fetchone()
        return row[0] if row else None

    @staticmethod
    def _listing_data(x):
        return {"id":x.id,"name":x.name,"price":x.price,"gender":x.gender.value,"location":x.location,"amenities":sorted(x.amenities),"source":x.source,"url":x.url}
    @staticmethod
    def _listing(x):
        return KosListing(x["id"],x["name"],x["price"],Gender(x["gender"]),x["location"],frozenset(x["amenities"]),x["source"],x["url"])
