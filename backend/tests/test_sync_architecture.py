"""Keep new business/sync paths behind the shared administrator-only factory."""
import ast
from pathlib import Path
import unittest


class SyncArchitectureTests(unittest.TestCase):
    def test_business_modules_cannot_construct_their_own_bitrix_clients(self):
        root = Path(__file__).resolve().parents[1] / "src" / "cr_portal"
        violations = []
        for area in ("api", "services", "workers"):
            for path in (root / area).rglob("*.py"):
                if path.relative_to(root).as_posix() == "api/v1/auth.py":
                    continue  # Only OAuth entry points may use transient user credentials.
                tree = ast.parse(path.read_text(encoding="utf-8-sig"))
                names = {"BitrixClient"}
                for node in ast.walk(tree):
                    if isinstance(node, ast.ImportFrom):
                        names.update(alias.asname or alias.name for alias in node.names if alias.name == "BitrixClient")
                for node in ast.walk(tree):
                    if isinstance(node, ast.Call) and (
                        isinstance(node.func, ast.Name) and node.func.id in names
                        or isinstance(node.func, ast.Attribute) and node.func.attr == "BitrixClient"
                    ):
                        violations.append(f"{path.relative_to(root)}:{node.lineno}")
        self.assertEqual(violations, [], "Use create_sync_client(session) / api.deps.bitrix_client")

    def test_all_existing_worker_paths_use_the_shared_factory(self):
        path = Path(__file__).resolve().parents[1] / "src" / "cr_portal" / "workers" / "sync.py"
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        for name in ("process_job", "process_nightly_sync", "process_daily_calculation"):
            function = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef) and node.name == name)
            calls = [node for node in ast.walk(function) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)]
            self.assertTrue(any(node.func.id == "create_sync_client" for node in calls), name)
