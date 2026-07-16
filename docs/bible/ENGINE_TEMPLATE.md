# ENGINE_TEMPLATE.md

Every engine follows this exact structure. AI agents must read this before building any engine.

---

## 1. Objective
*What does this engine do? One paragraph.*

## 2. Scope
*What is IN scope and OUT of scope.*

## 3. Dependencies
*Which engines does this depend on? (Reference 022_DEPENDENCY_GRAPH.md)*

## 4. Business Rules
*Which rules from 002_BUSINESS_RULES.md apply?*

## 5. Database Tables
*Schema name, tables, columns, indexes, constraints.*

## 6. Domain Models
*Entities, value objects, aggregate roots, invariants.*

## 7. API Endpoints
| Method | Path | Description | Auth | Rate Limit |

## 8. Events
| Event | Publisher | Consumers | Payload |

## 9. State Machine
*Valid states and transitions.*

## 10. Error Codes
*Which codes from 020_ERROR_CATALOG.md does this engine use?*

## 11. Security
*Permissions, roles, data access rules. (Reference 023_CAPABILITY_MATRIX.md)*

## 12. Configuration
*Which keys from 024_CONFIGURATION.md does this engine use?*

## 13. Tests
| Test Type | Coverage Target | What to Test |

## 14. Performance Targets
| Metric | Target |

## 15. Acceptance Criteria
*Checklist for marking this engine complete.*
