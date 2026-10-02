# Identity Engine — Import Rules

## Golden Rule

**Domain layer must NEVER import from application, infrastructure, or presentation.**

## Allowed Imports

| Source Module | Can Import From |
|---|---|
| `domain/**/*.py` | Python stdlib only |
| `application/**/*.py` | `domain.*` |
| `infrastructure/**/*.py` | `domain.*` |
| `presentation/**/*.py` | `application.*`, `domain.*` (entities for type hints) |
| `shared/domain/*.py` | Python stdlib only |
| `shared/application/*.py` | `shared.domain.*` |
| `shared/infrastructure/*.py` | `shared.domain.*` |
| `tests/**/*.py` | Everything (test only) |

## Prohibited Imports

```python
# NEVER do this:
from infrastructure... import ...   # in domain/
from presentation... import ...     # in domain/
from application... import ...      # in domain/
from infrastructure... import ...   # in application/
from presentation... import ...     # in application/

# ALWAYS do this:
from domain.identity.entities.user import User           # in application/
from domain.identity.ports.pin_hasher import PinHasher   # in infrastructure/
from application.identity.use_cases.login import LoginUseCase  # in presentation/
```

## Port Implementation Rule

Every port (Protocol) in `domain/identity/ports/` must have exactly one implementation in `infrastructure/identity/services/`.

| Port | Implementation |
|---|---|
| `PinHasher` | `BcryptPinHasher` |
| `TokenService` | `JwtTokenService` |
| `OtpService` | `OtpGeneratorService` |
| `EventPublisher` | `OutboxPublisher` |

## Naming Convention

| Layer | Files | Classes |
|---|---|---|
| Domain | `snake_case.py` | PascalCase |
| Application | `snake_case.py` | PascalCase + `UseCase` suffix |
| Infrastructure | `snake_case.py` | PascalCase |
| Presentation | `snake_case.py` | PascalCase + `Route`/`Middleware`/`Handler` suffix |

## Circular Dependency Detection

The CI pipeline uses `pytest-arch` to detect circular dependencies. To run locally:

```bash
pip install pytest-arch
pytest tests/unit/identity/test_architecture.py
```

## Architecture Test Example

```python
# tests/unit/identity/test_architecture.py
import pytest
from pytest_arch import ArchRule

class TestIdentityArchitecture:
    def test_domain_does_not_import_infrastructure(self):
        rule = ArchRule().modules("domain.identity.*").should_not(
            "import", "infrastructure.*"
        )
        rule.assert_satisfied()

    def test_application_imports_domain_only(self):
        rule = ArchRule().modules("application.identity.*").should_only(
            "import", "domain.*"
        )
        rule.assert_satisfied()

    def test_no_circular_dependencies(self):
        rule = ArchRule().no_circular_imports()
        rule.assert_satisfied()
```
