# kos-hunter

An OpenClaw agent for finding eligible kos listings, contacting landlords, and handing consequential decisions back to its user.

The project is currently an experimental, single-user tool. Its modular-monolith and ports-and-adapters boundaries are intended to support additional listing platforms and communication channels later.

## Safety

- Keep `IDENTITY.md`, platform sessions, cookies, generated shortlists, databases, logs, and landlord contact data local.
- Copy `IDENTITY.example.md` to `IDENTITY.md`; never commit the completed file.
- Store Mamikos session material under `~/.openclaw/kos-hunter/`, outside this repository.
- Tests must use fake adapters or sanitized fixtures. Live WhatsApp tests require an explicit test recipient.
- Mamikos integration is unofficial and may break or be restricted by platform terms. Review applicable terms before production or commercial use.

## Documentation

- Product and agent instructions: `AGENTS.md`
- Listing platform contract: `docs/PLATFORMS.md`
- Current Mamikos research: `docs/MAMIKOS_API.md`
- Architecture specification: [GitHub issue #1](https://github.com/faizsetiawan12/kos-hunter/issues/1)

## Current Status

The core modular-monolith foundation, ports-and-adapters architecture, SQLite persistence, Mamikos listing source adapter, OpenClaw entry point, WhatsApp approval outreach, conversation tracking, and negotiation approval gates are implemented with 41 passing unit and acceptance tests.

## Architecture

The system follows a ports-and-adapters design:
- `kos_hunter/domain.py`: Vendor-free domain models, criteria, ranking, and port definitions (`ListingSource`, `MessagingPort`, `NotificationPort`, `PersistencePort`, `ClockPort`).
- `kos_hunter/application.py`: Primary application facade coordinating search, hard eligibility, soft ranking, and contact enrichment.
- `kos_hunter/persistence.py`: SQLite persistence adapter for restart-safe search runs, normalized listings, and candidate rankings.
- `kos_hunter/openclaw.py`: OpenClaw conversational entry point with mutex concurrency guards and formatted shortlist outputs.
- `kos_hunter/outreach.py`: Approval-mode WhatsApp outreach job queue, 08:00–20:00 WIB rate-limiting, and idempotent send states.
- `kos_hunter/conversations.py`: Landlord reply tracking, chat fact extraction, and 48h follow-up policy.
- `kos_hunter/negotiation.py`: Polite negotiation, honest disclosure, and strict `ApprovalRequest` gates for survey/booking/payment handoff.
- `search/mamikos.py`: Listing source adapter for Mamikos with encrypted payload decryption and contact parsing.
- `cli.py`: Diagnostic CLI command (`search`) for direct operations and recovery.

## Development

Requires Python 3.10+. Run the standard-library test suite:

```bash
python3 -m unittest discover -s tests
```

Pytest is also supported when installed: `pytest`.
