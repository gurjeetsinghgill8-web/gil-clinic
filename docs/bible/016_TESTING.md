# 016 — TESTING

*Testing strategy, coverage targets, and test organization.*

---

## Testing Pyramid

```
     /\ 
    /E2E\        5%  — Playwright/Cypress (critical paths)
   /------\ 
  /Integration\ 15%  — pytest with test DB
 /--------------\ 
/  Unit Tests   \ 80%  — pytest (domain logic)
------------------
```

## Unit Tests

- Test every domain entity, value object, and service
- Mock all external dependencies (DB, Redis, AI providers)
- Use pytest fixtures for test data
- Minimum coverage: 90% (domain/), 80% (application/), 60% (infrastructure/)
- Test file naming: test_{module_name}.py
- One assert per test (ideally)

## Integration Tests

- Test DB repository implementations with test PostgreSQL
- Test API endpoints with TestClient (FastAPI built-in)
- Test event publishing and consumption
- Use transaction rollback between tests
- Seed minimal test data, not full DB

## E2E Tests

- Playwright for critical user journeys:
  - Patient registration -> queue -> doctor -> billing
  - Staff login -> call next -> complete token
  - Appointment booking -> reminder -> check-in
- Run against staging environment
- Weekly full run, smoke tests on every deploy

## Test Data Management

- Factory pattern for test data (factory_boy library)
- Separate test database (ghos_test)
- Migrations run before test suite
- Clean data between test runs
- No test data in production database ever
