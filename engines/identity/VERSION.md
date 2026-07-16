# Identity Engine — Version

**Current Version: 1.0.0**
**Status: FROZEN** — No changes without Architecture Decision Record (ADR)

---

## Version History

| Version | Date | Changes |
|---|---|---|
| 1.0.0 | 2026-07-12 | Initial stable release. Domain + Application layers complete. 9 use cases implemented. |

## Interface Version

All engines consuming the Identity Engine must target this interface version.

| Interface | Version | Status |
|---|---|---|
| Domain Events (IDENTITY.*) | 1.0.0 | Stable |
| Repository Ports | 1.0.0 | Stable |
| Use Case Contracts | 1.0.0 | Stable |
| DTOs (Request/Response) | 1.0.0 | Stable |

## Versioning Policy

- **MAJOR**: Breaking changes to published interfaces (events, ports, DTOs)
- **MINOR**: New use cases, non-breaking additions
- **PATCH**: Bug fixes, internal refactors, documentation

After freeze:
- Any change to a published interface requires an ADR
- Internal implementation changes (infrastructure) are patch-level
- New use cases are minor-level
