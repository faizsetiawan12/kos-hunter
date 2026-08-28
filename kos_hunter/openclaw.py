"""OpenClaw-facing search entry point.

The entry point deliberately depends only on the application facade and ports, so
registered OpenClaw agents can invoke the same use case as the CLI without shelling
out or making network calls in tests.
"""
from __future__ import annotations

from threading import Lock
from typing import Protocol

from .application import SearchFacade
from .domain import RankedListing, SearchCriteria


class NotificationPort(Protocol):
    def notify(self, message: str) -> None: ...


class SearchAlreadyRunning(RuntimeError):
    """Raised when a user asks for a search while one is already in progress."""


class OpenClawSearchEntryPoint:
    def __init__(self, facade: SearchFacade, notifications: NotificationPort):
        self.facade = facade
        self.notifications = notifications
        self._run_lock = Lock()

    def start_search(self, criteria: SearchCriteria) -> list[RankedListing]:
        if not self._run_lock.acquire(blocking=False):
            self.notifications.notify("Pencarian sedang berjalan. Permintaan ini tidak dijalankan dua kali.")
            raise SearchAlreadyRunning("a search is already running")
        try:
            self.notifications.notify("Pencarian dimulai.")
            try:
                results = self.facade.run(criteria)
            except Exception as exc:
                message = f"Pencarian gagal: {exc}. Coba lagi atau periksa koneksi/platform Mamikos."
                self.notifications.notify(message)
                raise
            self.notifications.notify(f"Pencarian selesai. Ditemukan {len(results)} kos yang sesuai.")
            self.notifications.notify(format_shortlist(results))
            return results
        finally:
            self._run_lock.release()

    # Friendly alias for OpenClaw tool registries.
    def search(self, criteria: SearchCriteria) -> list[RankedListing]:
        return self.start_search(criteria)


def format_shortlist(results: list[RankedListing]) -> str:
    if not results:
        return "Belum ada kos yang memenuhi kriteria."
    lines = ["**Shortlist kos:**"]
    for index, ranked in enumerate(results, 1):
        listing = ranked.listing
        reasons = ", ".join(ranked.reasons)
        link = f" — [Lihat listing]({listing.url})" if listing.url else ""
        lines.append(f"{index}. **{listing.name}** — Rp{listing.price:,}/bulan ({listing.location}){link}")
        lines.append(f"   Alasan: {reasons}")
    return "\n".join(lines)
