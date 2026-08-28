#!/usr/bin/env python3
"""
kos-hunter CLI

Usage:
  python -m kos_hunter search [--area kukel] [--price-max 2000000] [--all-areas]
  python -m kos_hunter contacts --area kukel   # add phone numbers to shortlist
"""

import argparse
import json
import sys
import time
from pathlib import Path

from search.mamikos import MamikosAdapter, AREAS, KosListing

SHORTLIST_FILE = Path(__file__).parent / "shortlist.json"
GENDER_MAP = {0: "campur", 1: "putra", 2: "putri"}
FAC_LABELS = {1: "KMD", 8: "air panas", 13: "AC", 742: "wifi", 84: "listrik incl.", 23: "parkir motor"}


def fmt_listing(i: int, l: KosListing) -> str:
    facs = [FAC_LABELS[f] for f in l.fac_room_ids if f in FAC_LABELS]
    fac_str = ", ".join(facs) if facs else "-"
    avail = "✓" if l.available else "✗"
    rating = f"{l.rating:.1f}★" if l.rating else "no rating"
    contact = l.contact or "(no phone yet)"
    return (
        f"{i:>3}. [{avail}] {l.title}\n"
        f"     {l.price_str}/bln | {GENDER_MAP.get(l.gender,'?')} | {l.area_label}\n"
        f"     Fasilitas: {fac_str} | {rating} ({l.review_count} ulasan)\n"
        f"     {l.url}\n"
        f"     📞 {contact}"
    )


def cmd_search(args: argparse.Namespace) -> None:
    adapter = MamikosAdapter()

    if not adapter.health_check():
        print("⚠  Session expired — refreshing...")
        try:
            adapter.refresh_session()
        except Exception as e:
            print(f"✗ Refresh failed: {e}")
            sys.exit(1)

    areas = list(AREAS.keys()) if args.all_areas else [args.area]
    all_listings: list[KosListing] = []

    for area in areas:
        label = AREAS[area]["label"]
        print(f"\n🔍 Searching {label}...")
        listings = adapter.search(area=area, price_max=args.price_max)
        print(f"   Found {len(listings)} listings")
        all_listings.extend(listings)

    # Deduplicate by platform_id
    seen: set[str] = set()
    unique: list[KosListing] = []
    for l in all_listings:
        if l.platform_id not in seen:
            seen.add(l.platform_id)
            unique.append(l)

    # Rank: available first → rating desc → price asc
    unique.sort(key=lambda l: (not l.available, -(l.rating or 0), l.price_monthly))

    print(f"\n{'─'*60}")
    print(f"  {len(unique)} eligible kos found\n")
    for i, l in enumerate(unique, 1):
        print(fmt_listing(i, l))
        print()

    # Save shortlist
    data = [
        {
            "rank":          i,
            "platform":      l.platform,
            "platform_id":   l.platform_id,
            "title":         l.title,
            "url":           l.url,
            "price_monthly": l.price_monthly,
            "gender":        l.gender,
            "area_label":    l.area_label,
            "available":     l.available,
            "fac_room_ids":  l.fac_room_ids,
            "fac_share_ids": l.fac_share_ids,
            "rating":        l.rating,
            "review_count":  l.review_count,
            "contact":       l.contact,
        }
        for i, l in enumerate(unique, 1)
    ]
    SHORTLIST_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    print(f"💾 Shortlist saved → {SHORTLIST_FILE}")


def cmd_contacts(args: argparse.Namespace) -> None:
    if not SHORTLIST_FILE.exists():
        print("✗ No shortlist found. Run `search` first.")
        sys.exit(1)

    adapter = MamikosAdapter()
    data = json.loads(SHORTLIST_FILE.read_text())

    print(f"📞 Fetching phone numbers for {len(data)} listings (3s delay each)...\n")
    updated = 0
    for entry in data:
        if entry.get("contact"):
            continue   # already have it
        listing = KosListing(
            platform      = entry["platform"],
            platform_id   = entry["platform_id"],
            title         = entry["title"],
            url           = entry["url"],
            price_monthly = entry["price_monthly"],
            gender        = entry["gender"],
            area_label    = entry["area_label"],
            address       = "",
            available     = entry["available"],
            fac_room_ids  = entry["fac_room_ids"],
            fac_share_ids = entry["fac_share_ids"],
            rating        = entry["rating"],
            review_count  = entry["review_count"],
            contact       = "",
        )
        phone = adapter.get_contact(listing)
        entry["contact"] = phone
        status = f"📱 {phone}" if phone else "✗ not found"
        print(f"  [{entry['rank']:>3}] {entry['title'][:50]:<50} {status}")
        updated += 1
        time.sleep(3)

    SHORTLIST_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    print(f"\n💾 Shortlist updated → {SHORTLIST_FILE}  ({updated} fetched)")


def main() -> None:
    parser = argparse.ArgumentParser(prog="kos-hunter")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_search = sub.add_parser("search", help="Search Mamikos and produce shortlist")
    p_search.add_argument("--area",      default="kukel", choices=list(AREAS))
    p_search.add_argument("--price-max", type=int, default=2_000_000)
    p_search.add_argument("--all-areas", action="store_true",
                          help="Search all areas and deduplicate")

    p_contacts = sub.add_parser("contacts", help="Fetch phone numbers for shortlist")
    p_contacts.add_argument("--area", default="kukel")  # unused, for consistency

    args = parser.parse_args()
    {"search": cmd_search, "contacts": cmd_contacts}[args.cmd](args)


if __name__ == "__main__":
    main()
