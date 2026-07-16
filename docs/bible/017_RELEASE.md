# 017 — RELEASE

*Versioning, release workflow, and compatibility policy.*

---

## Versioning

Semantic Versioning (MAJOR.MINOR.PATCH):
- MAJOR: Breaking API changes, DB schema changes requiring migration
- MINOR: New features, new endpoints, non-breaking additions
- PATCH: Bug fixes, security patches, minor improvements

Current version: 2.0.0-alpha

## Release Workflow

1. Feature branch from develop
2. PR to develop after implementation + tests
3. Staging deploy from develop
4. QA on staging
5. PR from develop to main (release candidate)
6. Tag version on main (v2.x.x)
7. Production deploy from main
8. Release notes in CHANGELOG.md

## Hotfix Process

1. Branch from main: hotfix/{description}
2. Fix + test
3. PR directly to main (skip develop)
4. Cherry-pick to develop
5. Tag patch version
6. Deploy

## Compatibility Policy

- API version via URL path (/api/v1/, /api/v2/)
- Deprecated endpoints supported for 2 minor versions
- DB migrations backward compatible for 1 minor version
- Event schema versioned in payload
- Breaking changes announced 1 minor version in advance
