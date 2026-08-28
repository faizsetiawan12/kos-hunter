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

The existing code is a research prototype. The architecture in issue #1 is the implementation target, not a claim that the current prototype is production-ready.

## Development

Requires Python 3.10+. Run the standard-library test suite:

```bash
python3 -m unittest discover -s tests
```

Pytest is also supported when installed: `pytest`.
