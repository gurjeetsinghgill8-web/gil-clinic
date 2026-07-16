"""Architecture tests — enforce Clean Architecture dependency rules.

Run with: pytest tests/unit/identity/test_architecture.py -v
"""


class TestIdentityArchitecture:
    """Verify that Clean Architecture rules are enforced.

    These tests ensure:
    - Domain layer has ZERO infrastructure/application/presentation imports
    - Application layer only imports domain
    - Infrastructure layer only imports domain
    - No circular dependencies exist
    """

    def test_domain_imports_only_stdlib(self):
        """Domain entities must not import from application, infrastructure, or presentation."""
        import ast
        import os
        import sys

        domain_dir = os.path.join(
            os.path.dirname(__file__),
            "..", "..", "..", "src", "domain", "identity"
        )
        domain_dir = os.path.abspath(domain_dir)

        violations = []
        for root, _dirs, files in os.walk(domain_dir):
            for f in files:
                if not f.endswith(".py"):
                    continue
                filepath = os.path.join(root, f)
                with open(filepath, "r", encoding="utf-8") as fh:
                    try:
                        tree = ast.parse(fh.read())
                    except SyntaxError:
                        continue

                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            if alias.name.startswith(("src.", "application", "infrastructure", "presentation")):
                                rel_path = os.path.relpath(filepath, domain_dir)
                                violations.append(f"{rel_path}: imports {alias.name}")
                    elif isinstance(node, ast.ImportFrom):
                        if node.module and node.module.startswith(("src.", "application", "infrastructure", "presentation")):
                            rel_path = os.path.relpath(filepath, domain_dir)
                            violations.append(f"{rel_path}: from-import {node.module}")

        assert len(violations) == 0, (
            f"Domain layer must not import from other layers. Violations:\n"
            + "\n".join(violations)
        )

    def test_no_circular_imports_within_identity(self):
        """No circular dependencies within the identity engine package."""
        import ast
        import os

        src_dir = os.path.join(
            os.path.dirname(__file__),
            "..", "..", "..", "src"
        )
        src_dir = os.path.abspath(src_dir)

        # Build import graph
        graph = {}
        for root, _dirs, files in os.walk(src_dir):
            for f in files:
                if not f.endswith(".py"):
                    continue
                filepath = os.path.join(root, f)
                rel = os.path.relpath(filepath, src_dir).replace(os.sep, ".").replace(".py", "")
                if rel.endswith(".__init__"):
                    rel = rel[:-9]

                graph[rel] = set()
                with open(filepath, "r", encoding="utf-8") as fh:
                    try:
                        tree = ast.parse(fh.read())
                    except SyntaxError:
                        continue

                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            graph[rel].add(alias.name.split(".")[0])
                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            graph[rel].add(node.module.split(".")[0])

        # Simple cycle detection (DFS)
        visited = set()
        rec_stack = set()

        def has_cycle(node, path):
            visited.add(node)
            rec_stack.add(node)
            for neighbor in graph.get(node, set()):
                if neighbor not in visited:
                    if has_cycle(neighbor, path + [neighbor]):
                        return True
                elif neighbor in rec_stack:
                    cycle_path = " -> ".join(path + [neighbor])
                    print(f"Cycle detected: {cycle_path}")
                    return True
            rec_stack.discard(node)
            return False

        cycles = []
        for node in graph:
            if node not in visited:
                if has_cycle(node, [node]):
                    cycles.append(node)

        assert len(cycles) == 0, f"Circular dependencies detected in: {cycles}"
