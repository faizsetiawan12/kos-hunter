"""
WhatsApp outreach message templates.

All messages are in Bahasa Indonesia, santai-formal tone.
"""

from dataclasses import dataclass


@dataclass
class KosInfo:
    title: str
    price_str: str      # e.g. "Rp1.500.000"
    area_label: str


# ── Opening message ────────────────────────────────────────────────────────────

def opening(kos: KosInfo, tenant_name: str) -> str:
    return (
        f"Halo, permisi 🙏\n\n"
        f"Saya {tenant_name}, mau tanya-tanya soal kos *{kos.title}*. "
        f"Apakah kamarnya masih tersedia untuk bulan Oktober?\n\n"
        f"Terima kasih 🙏"
    )


# ── Follow-up if no reply after 2 days ────────────────────────────────────────

def followup_no_reply(kos: KosInfo) -> str:
    return (
        f"Halo, permisi 🙏 Mau follow-up sebentar soal kos *{kos.title}*. "
        f"Apakah masih tersedia?\n"
        f"Terima kasih"
    )


# ── Availability confirmed → ask facilities ────────────────────────────────────

def ask_facilities() -> str:
    return (
        "Terima kasih infonya 🙏\n\n"
        "Boleh tanya:\n"
        "- Ada AC?\n"
        "- Kamar mandi dalam?\n"
        "- Air panas?\n"
        "- WiFi?\n"
        "- Listrik termasuk atau token sendiri?\n\n"
        "Dan parkir motor apakah tersedia?"
    )


# ── Negotiate price ────────────────────────────────────────────────────────────

def negotiate_price(listed_price_str: str, duration_months: int) -> str:
    return (
        f"Untuk harga {listed_price_str}/bulan, "
        f"apakah bisa didiskusikan? 🙏\n"
        f"Rencana saya sewa {duration_months} bulan, sendiri, tidak merokok."
    )


# ── Negotiate price — offer extras instead ────────────────────────────────────

def negotiate_extras() -> str:
    return (
        "Kalau harganya belum bisa turun, "
        "apakah bisa dibantu misalnya token listrik bulan pertama, "
        "atau deposit bisa dicicil? 🙏"
    )


# ── Walk away politely ─────────────────────────────────────────────────────────

def walk_away() -> str:
    return (
        "Baik, terima kasih banyak atas infonya 🙏\n"
        "Maaf belum bisa cocok untuk saat ini. "
        "Semoga kostnya cepat terisi ya."
    )


# ── Schedule survey ────────────────────────────────────────────────────────────

def request_survey(slots: list[str]) -> str:
    slot_lines = "\n".join(f"- {s}" for s in slots)
    return (
        f"Boleh saya survey dulu sebelum memutuskan? 🙏\n\n"
        f"Saya tersedia di:\n{slot_lines}\n\n"
        f"Apakah ada waktu yang cocok?"
    )


# ── Honest bot disclosure (only if directly asked) ─────────────────────────────

def bot_disclosure(tenant_name: str) -> str:
    return (
        f"Ini asisten yang membantu {tenant_name} carikan kos. "
        f"Untuk konfirmasi dan keputusan final, {tenant_name} yang akan langsung followup 🙏"
    )
