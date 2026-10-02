#!/usr/bin/env python3
"""
Identity Engine Skeleton -- 15-Point Validation Gate
Runs every check and produces a PASS/FAIL report.
"""

import os
import sys
import glob
import ast
from collections import defaultdict

ROOT = r"C:\Users\pc\Desktop\gurjas ai\GIL CLINIC"
SRC = os.path.join(ROOT, "src")

results = []  # list of (check_name, status, detail)


def check(name, condition, detail=""):
    """Record a PASS or FAIL."""
    status = "PASS" if condition else "FAIL"
    results.append((name, status, detail))
    return condition


def section(title):
    results.append((f"--- {title} ---", "", ""))


# ---------------------------------------------------------------------------
# 1. Clean Architecture Dependency Rules
# ---------------------------------------------------------------------------
section("1. Clean Architecture Dependency Rules")

# Collect all .py files (excluding __init__.py) grouped by layer
def get_all_py_files_under(path):
    files = []
    for root_dir, dirs, fnames in os.walk(path):
        for f in fnames:
            if f.endswith(".py"):
                files.append(os.path.join(root_dir, f))
    return sorted(files)


all_py_files = get_all_py_files_under(SRC)

domain_files = []
application_files = []
infrastructure_files = []
presentation_files = []
other_files = []

for fp in all_py_files:
    rel = os.path.relpath(fp, SRC).replace("\\", "/")
    if rel.startswith("domain/"):
        domain_files.append(fp)
    elif rel.startswith("application/"):
        application_files.append(fp)
    elif rel.startswith("infrastructure/"):
        infrastructure_files.append(fp)
    elif rel.startswith("presentation/"):
        presentation_files.append(fp)
    else:
        other_files.append(fp)

violations = []


def get_imports(filepath):
    """Return set of module-level imported package names."""
    imports = set()
    try:
        with open(filepath, "r", encoding="utf-8") as fh:
            content = fh.read()
        if not content.strip():
            return imports  # empty file
        tree = ast.parse(content)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module.split(".")[0])
    except (SyntaxError, Exception) as e:
        violations.append(f"  PARSE ERROR: {filepath} -> {e}")
    return imports


def layer_tag(fp):
    rel = os.path.relpath(fp, SRC).replace("\\", "/")
    if rel.startswith("domain/"):
        return "domain"
    elif rel.startswith("application/"):
        return "application"
    elif rel.startswith("infrastructure/"):
        return "infrastructure"
    elif rel.startswith("presentation/"):
        return "presentation"
    return "other"


def belongs_to_layer(import_name, layer):
    """Check if the import refers to a package under src/<layer>/."""
    pkg_path = os.path.join(SRC, layer)
    import_path = os.path.join(SRC, import_name)
    return os.path.exists(pkg_path) and os.path.commonpath([pkg_path, import_path]) == pkg_path


for fp in domain_files:
    layer = layer_tag(fp)
    imports = get_imports(fp)
    for imp in imports:
        if belongs_to_layer(imp, "application") or belongs_to_layer(imp, "infrastructure") or belongs_to_layer(imp, "presentation"):
            violations.append(f"  DOMAIN file imports from outer layer: {fp} -> {imp}")

for fp in application_files:
    imports = get_imports(fp)
    for imp in imports:
        if belongs_to_layer(imp, "infrastructure") or belongs_to_layer(imp, "presentation"):
            violations.append(f"  APPLICATION file imports from outer layer: {fp} -> {imp}")

for fp in infrastructure_files:
    imports = get_imports(fp)
    for imp in imports:
        if belongs_to_layer(imp, "application") or belongs_to_layer(imp, "presentation"):
            violations.append(f"  INFRASTRUCTURE file imports from outer layer: {fp} -> {imp}")

# Presentation may import from application or domain - no restrictions beyond that

dep_rule_pass = len(violations) == 0
detail = "\n".join(violations) if violations else "No violations found"
check("1a - Domain does not import application/infrastructure/presentation", dep_rule_pass, detail)

# Also count file-level pass
check("1 - Clean Architecture Dependency Rules (all layers)", len(violations) == 0,
      f"{len(violations)} violation(s)" if violations else "All files conform to dependency rules")

# ---------------------------------------------------------------------------
# 2. Folder Structure
# ---------------------------------------------------------------------------
section("2. Folder Structure")

expected_folders = [
    "src/domain/identity/entities",
    "src/domain/identity/events",
    "src/domain/identity/exceptions",
    "src/domain/identity/ports",
    "src/domain/identity/services",
    "src/domain/identity/value_objects",
    "src/application/identity/dtos",
    "src/application/identity/interfaces",
    "src/application/identity/use_cases",
    "src/infrastructure/identity/config",
    "src/infrastructure/identity/events",
    "src/infrastructure/identity/models",
    "src/infrastructure/identity/repositories",
    "src/infrastructure/identity/services",
    "src/presentation/identity/dependencies",
    "src/presentation/identity/errors",
    "src/presentation/identity/middleware",
    "src/presentation/identity/routes",
    "src/presentation/identity/schemas",
    "src/shared/domain",
    "src/shared/application",
    "src/shared/infrastructure",
]

missing_folders = []
for rel_path in expected_folders:
    full_path = os.path.join(ROOT, rel_path)
    if not os.path.isdir(full_path):
        missing_folders.append(rel_path)

existing_folders = [f for f in expected_folders if f not in missing_folders]
check("2 - All expected folders exist", len(missing_folders) == 0,
      f"Missing: {missing_folders}" if missing_folders else f"All {len(expected_folders)} folders present")

# ---------------------------------------------------------------------------
# 3. Package Structure (__init__.py)
# ---------------------------------------------------------------------------
section("3. Package Structure (__init__.py)")

dirs_with_py = set()
for fp in all_py_files:
    dirs_with_py.add(os.path.dirname(fp))

missing_init = []
for d in sorted(dirs_with_py):
    init_file = os.path.join(d, "__init__.py")
    if not os.path.isfile(init_file):
        rel_d = os.path.relpath(d, ROOT)
        missing_init.append(rel_d)

# Also check shared root has __init__
shared_root = os.path.join(SRC, "shared")
shared_init = os.path.join(shared_root, "__init__.py")
if os.path.isdir(shared_root) and not os.path.isfile(shared_init):
    missing_init.append("src/shared/ (no __init__.py)")

check("3 - Every directory with .py files has __init__.py", len(missing_init) == 0,
      f"Missing __init__.py in: {missing_init}" if missing_init else "All packages are intact")

# ---------------------------------------------------------------------------
# 4. Import Dependency Graph + Circular Dependencies
# ---------------------------------------------------------------------------
section("4. Import Dependency Graph & Circular Dependencies")

# Build a graph: module -> [dependencies]
graph = {}
for fp in all_py_files:
    rel = os.path.relpath(fp, SRC).replace("\\", "/")
    graph[rel] = set()
    for imp in get_imports(fp):
        # Check if this import maps to a src/ package
        import_path = os.path.join(SRC, imp)
        if os.path.isdir(import_path):
            # Find any .py files under that path
            for dep_file in glob.glob(os.path.join(import_path, "**/*.py"), recursive=True):
                dep_rel = os.path.relpath(dep_file, SRC).replace("\\", "/")
                graph[rel].add(dep_rel)

# Detect cycles using DFS
cycle_found = False
cycle_details = []
WHITE, GRAY, BLACK = 0, 1, 2
color = {node: WHITE for node in graph}
parent = {}

def dfs_visit(node, path):
    global cycle_found
    color[node] = GRAY
    for neighbor in graph.get(node, set()):
        if neighbor not in color:
            color[neighbor] = WHITE
        if color[neighbor] == GRAY:
            # Found a cycle
            cycle_found = True
            cycle_path = path + [neighbor]
            idx = cycle_path.index(neighbor)
            cycle_str = " -> ".join(cycle_path[idx:]) + f" -> {neighbor}"
            cycle_details.append(f"Cycle: {cycle_str}")
        elif color[neighbor] == WHITE:
            dfs_visit(neighbor, path + [neighbor])
    color[node] = BLACK

for node in list(graph.keys()):
    if color[node] == WHITE:
        dfs_visit(node, [node])

check("4a - No circular dependencies", not cycle_found,
      "\n".join(cycle_details) if cycle_details else "No circular dependencies found")

# Print dependency map
dep_map_lines = ["Dependency Map:"]
for mod, deps in sorted(graph.items()):
    if deps:
        dep_map_lines.append(f"  {mod} -> {', '.join(sorted(deps))}")
    else:
        dep_map_lines.append(f"  {mod} -> (none)")

check("4b - Dependency map generated", True, "\n".join(dep_map_lines))
check("4 - Import Dependency Graph", not cycle_found,
      "Circular dependencies detected" if cycle_found else "No cycles. Map generated.")

# ---------------------------------------------------------------------------
# 5. Configuration
# ---------------------------------------------------------------------------
section("5. Configuration")

configs_dir = os.path.join(ROOT, "configs")
configs_exist = os.path.isdir(configs_dir)
check("5a - configs/ directory exists", configs_exist)

dev_yaml = os.path.isfile(os.path.join(configs_dir, "development.yaml"))
prod_yaml = os.path.isfile(os.path.join(configs_dir, "production.yaml"))
test_yaml = os.path.isfile(os.path.join(configs_dir, "testing.yaml"))

missing_configs = []
if not dev_yaml:
    missing_configs.append("development.yaml")
if not prod_yaml:
    missing_configs.append("production.yaml")
if not test_yaml:
    missing_configs.append("testing.yaml")

check("5b - dev/prod/test YAML configs", dev_yaml and prod_yaml and test_yaml,
      f"Missing: {missing_configs}" if missing_configs else "All three config files present")
check("5 - Configuration", configs_exist and dev_yaml and prod_yaml and test_yaml,
      "Configuration check complete")

# ---------------------------------------------------------------------------
# 6. Logging
# ---------------------------------------------------------------------------
section("6. Logging")

logging_file = os.path.join(SRC, "shared", "infrastructure", "logging.py")
check("6 - src/shared/infrastructure/logging.py exists", os.path.isfile(logging_file))

# ---------------------------------------------------------------------------
# 7. Error Handling
# ---------------------------------------------------------------------------
section("7. Error Handling")

exceptions_dir = os.path.join(SRC, "domain", "identity", "exceptions")
check("7 - src/domain/identity/exceptions/ directory exists", os.path.isdir(exceptions_dir))

if os.path.isdir(exceptions_dir):
    exc_files = [f for f in os.listdir(exceptions_dir) if f.endswith(".py") and f != "__init__.py"]
    check("7b - Exception files present", len(exc_files) > 0,
          f"Files: {exc_files}" if exc_files else "No exception files found")

# ---------------------------------------------------------------------------
# 8. Event Infrastructure
# ---------------------------------------------------------------------------
section("8. Event Infrastructure")

event_publisher = os.path.join(SRC, "domain", "identity", "ports", "event_publisher.py")
check("8a - src/domain/identity/ports/event_publisher.py exists", os.path.isfile(event_publisher))

infra_events_dir = os.path.join(SRC, "infrastructure", "identity", "events")
check("8b - src/infrastructure/identity/events/ directory exists", os.path.isdir(infra_events_dir))

if os.path.isdir(infra_events_dir):
    event_files = [f for f in os.listdir(infra_events_dir) if f.endswith(".py")]
    check("8c - Event stub files present", len(event_files) > 1,
          f"Files: {event_files}" if event_files else "No event files found")

check("8 - Event Infrastructure",
      os.path.isfile(event_publisher) and os.path.isdir(infra_events_dir),
      "Event infrastructure check complete")

# ---------------------------------------------------------------------------
# 9. Repository Interfaces
# ---------------------------------------------------------------------------
section("9. Repository Interfaces")

ports_dir = os.path.join(SRC, "domain", "identity", "ports")
if os.path.isdir(ports_dir):
    port_files = [f for f in os.listdir(ports_dir) if f.endswith(".py") and f != "__init__.py"]
    # Expected: event_publisher.py, otp_service.py, pin_hasher.py, token_service.py
    check("9a - Port definitions in domain/ports", len(port_files) >= 4,
          f"Found {len(port_files)} port files: {port_files}")
else:
    check("9a - Port definitions in domain/ports", False, "ports directory missing")

repos_dir = os.path.join(SRC, "infrastructure", "identity", "repositories")
if os.path.isdir(repos_dir):
    repo_files = [f for f in os.listdir(repos_dir) if f.endswith(".py") and f != "__init__.py"]
    check("9b - Stub repository implementations", len(repo_files) >= 3,
          f"Found {len(repo_files)} repository files: {repo_files}")
else:
    check("9b - Stub repository implementations", False, "repositories directory missing")

check("9 - Repository Interfaces",
      os.path.isdir(ports_dir) and os.path.isdir(repos_dir),
      "Repository interface check complete")

# ---------------------------------------------------------------------------
# 10. Documentation
# ---------------------------------------------------------------------------
section("10. Documentation")

doc_files = {
    "src/identity_README.md": os.path.isfile(os.path.join(SRC, "identity_README.md")),
    "src/ARCHITECTURE.md": os.path.isfile(os.path.join(SRC, "ARCHITECTURE.md")),
    "src/DEPENDENCY_MAP.md": os.path.isfile(os.path.join(SRC, "DEPENDENCY_MAP.md")),
    "src/IMPORT_RULES.md": os.path.isfile(os.path.join(SRC, "IMPORT_RULES.md")),
}

missing_docs = [k for k, v in doc_files.items() if not v]
check("10 - All documentation files exist", len(missing_docs) == 0,
      f"Missing: {missing_docs}" if missing_docs else "All 4 documentation files present")

# ---------------------------------------------------------------------------
# 11. Code Quality Config
# ---------------------------------------------------------------------------
section("11. Code Quality Config")

check("11a - pyproject.toml exists", os.path.isfile(os.path.join(ROOT, "pyproject.toml")))
check("11b - requirements.txt exists", os.path.isfile(os.path.join(ROOT, "requirements.txt")))
check("11 - Code Quality Config",
      os.path.isfile(os.path.join(ROOT, "pyproject.toml")) and
      os.path.isfile(os.path.join(ROOT, "requirements.txt")),
      "Both config files present")

# ---------------------------------------------------------------------------
# 12. Docker
# ---------------------------------------------------------------------------
section("12. Docker")

docker_dir = os.path.join(ROOT, "docker", "identity")
dockerfile = os.path.join(docker_dir, "Dockerfile")
compose = os.path.join(docker_dir, "docker-compose.yml")

check("12a - docker/identity/Dockerfile exists", os.path.isfile(dockerfile))
check("12b - docker/identity/docker-compose.yml exists", os.path.isfile(compose))
check("12 - Docker", os.path.isfile(dockerfile) and os.path.isfile(compose),
      "Both Docker files present")

# ---------------------------------------------------------------------------
# 13. CI/CD
# ---------------------------------------------------------------------------
section("13. CI/CD")

github_workflows = os.path.join(ROOT, ".github", "workflows")
ci_cd_exists = os.path.isdir(github_workflows)
if ci_cd_exists:
    wf_files = [f for f in os.listdir(github_workflows) if f.endswith((".yml", ".yaml"))]
    check("13 - CI/CD (.github/workflows/)", True,
          f"Present with {len(wf_files)} workflow file(s): {wf_files}")
else:
    check("13 - CI/CD (.github/workflows/)", True,
          "NOTE: .github/workflows/ does not exist (not a FAIL per spec)")

# ---------------------------------------------------------------------------
# 14. Security
# ---------------------------------------------------------------------------
section("14. Security")

check("14a - .env.example exists", os.path.isfile(os.path.join(ROOT, ".env.example")))
check("14b - .gitignore exists", os.path.isfile(os.path.join(ROOT, ".gitignore")))
check("14 - Security",
      os.path.isfile(os.path.join(ROOT, ".env.example")) and
      os.path.isfile(os.path.join(ROOT, ".gitignore")),
      "Security files present")

# ---------------------------------------------------------------------------
# 15. Shared Kernel
# ---------------------------------------------------------------------------
section("15. Shared Kernel")

shared_dirs = {
    "src/shared/domain": os.path.isdir(os.path.join(SRC, "shared", "domain")),
    "src/shared/application": os.path.isdir(os.path.join(SRC, "shared", "application")),
    "src/shared/infrastructure": os.path.isdir(os.path.join(SRC, "shared", "infrastructure")),
}

missing_shared = [k for k, v in shared_dirs.items() if not v]
check("15a - All shared kernel directories exist", len(missing_shared) == 0,
      f"Missing: {missing_shared}" if missing_shared else "All 3 shared dirs present")

# Check for files in shared kernel
shared_files = []
for sd in shared_dirs:
    full_sd = os.path.join(SRC, sd.replace("src/", ""))
    py_files = [f for f in os.listdir(full_sd) if f.endswith(".py") and f != "__init__.py"]
    shared_files.extend([os.path.join(sd, f) for f in py_files])

check("15b - Shared kernel has content files", len(shared_files) > 0,
      f"Files: {shared_files}" if shared_files else "No content files in shared kernel")

check("15 - Shared Kernel",
      all(shared_dirs.values()) and len(shared_files) > 0,
      "Shared kernel check complete")


# ===========================================================================
# REPORT
# ===========================================================================
print("=" * 72)
print("  IDENTITY ENGINE SKELETON -- 15-POINT VALIDATION GATE REPORT")
print("=" * 72)

all_pass = True
current_section = ""
for name, status, detail in results:
    if name.startswith("---"):
        print(f"\n{name}")
        continue
    if status == "":
        continue
    is_fail = status == "FAIL"
    if is_fail:
        all_pass = False
    symbol = "[PASS]" if status == "PASS" else "[FAIL]"
    print(f"  {symbol} {name}")
    if detail and is_fail:
        for line in detail.split("\n"):
            if line.strip():
                print(f"         {line.strip()}")

print()
print("=" * 72)

# Count checks (excluding section headers)
check_count = sum(1 for n, s, _ in results if s and not n.startswith("---"))
pass_count = sum(1 for _, s, _ in results if s == "PASS")
fail_count = sum(1 for _, s, _ in results if s == "FAIL")

print(f"\n  Results: {pass_count} PASS, {fail_count} FAIL, {check_count} total checks")
print()

if all_pass:
    print("  >>> Identity Skeleton Approved <<<")
    print("  All 15 points pass validation.")
else:
    print("  >>> GATE FAILED <<<")
    print("  The following checks FAILED:")
    for name, status, detail in results:
        if status == "FAIL":
            print(f"    - {name}")
            if detail:
                for line in detail.split("\n"):
                    if line.strip():
                        print(f"      {line.strip()}")

print()
print("=" * 72)
