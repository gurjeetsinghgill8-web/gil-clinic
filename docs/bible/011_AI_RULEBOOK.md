# 011 — AI RULEBOOK

*Rules for AI code generation agents.*
*All AI agents must follow these rules strictly.*

---

## Code Generation Rules

| Rule | Description |
|---|---|
| AI-CODE-001 | Always read the relevant Bible documents before writing code |
| AI-CODE-002 | Never hallucinate APIs, functions, or libraries that do not exist |
| AI-CODE-003 | Never hardcode secrets, API keys, or credentials in code |
| AI-CODE-004 | Write type hints for all Python function signatures |
| AI-CODE-005 | Write docstrings for all public functions and classes |
| AI-CODE-006 | Maximum file length: 500 lines. Split into modules if longer. |
| AI-CODE-007 | Each file has exactly one primary responsibility (Single Responsibility Principle) |
| AI-CODE-008 | Follow Clean Architecture: domain -> application -> infrastructure -> presentation |
| AI-CODE-009 | Domain layer has ZERO imports from frameworks (no FastAPI, no SQLAlchemy, no Streamlit) |
| AI-CODE-010 | Every function handles errors gracefully (try/except with meaningful messages) |
| AI-CODE-011 | Every external call has timeout, retry, and circuit breaker |
| AI-CODE-012 | No print() in production code — use proper logging |
| AI-CODE-013 | Constants and config go in config.py or environment variables, never inline |
| AI-CODE-014 | SQL queries use parameterized statements (no string concatenation) |
| AI-CODE-015 | All PII data is encrypted before storage or logging |
| AI-CODE-016 | Events are published after DB commit (outbox pattern) |
| AI-CODE-017 | Every state transition validates the transition is allowed |
| AI-CODE-018 | Never mutate function arguments — create new objects |
| AI-CODE-019 | Use UUIDv7 for all primary keys |
| AI-CODE-020 | All monetary values use Decimal type, never float |

## Prompting Rules (for AI agents prompting other AIs)

| Rule | Description |
|---|---|
| AI-PROMPT-001 | Always reference the relevant Bible document IDs in prompts |
| AI-PROMPT-002 | Each prompt must specify which BUSINESS_RULES apply |
| AI-PROMPT-003 | Each prompt must specify which EVENTS to publish |
| AI-PROMPT-004 | Each prompt must specify error codes from ERROR_CATALOG |
| AI-PROMPT-005 | Never use vague terms like 'appropriate error handling' — be specific |
| AI-PROMPT-006 | Include example inputs and outputs in prompts |
| AI-PROMPT-007 | Specify file paths and module boundaries in prompts |
| AI-PROMPT-008 | Include testing requirements in each prompt |

## Response Quality Rules

| Rule | Description |
|---|---|
| AI-OUT-001 | Always show file path and line count for each file generated |
| AI-OUT-002 | Always show test results after implementation |
| AI-OUT-003 | If a change breaks existing tests, explain why before fixing |
| AI-OUT-004 | If unsure about a business rule, reference BUSINESS_RULES.md, do not guess |
| AI-OUT-005 | When refactoring, list all files affected before making changes |
| AI-OUT-006 | For security-critical code, explicitly state what security measures were applied |

## Prohibited Patterns

- No AI generates final diagnosis or treatment plan without doctor signature
- No AI stores patient data for training purposes
- No AI code that can be exploited for SQL injection
- No AI code that logs PII in plain text
- No AI code with hardcoded IPs or URLs for production
- No AI code that bypasses authentication or authorization
- No AI code that modifies audit logs
