import ast, pathlib, unittest
class BoundaryTests(unittest.TestCase):
    def test_domain_has_no_vendor_imports(self):
        tree = ast.parse(pathlib.Path("kos_hunter/domain.py").read_text())
        forbidden = ("mamikos", "openclaw", "whatsapp", "telegram", "requests", "http", "sql", "psycopg", "sqlite")
        for node in ast.walk(tree):
            if isinstance(node, ast.Import): names = [x.name for x in node.names]
            elif isinstance(node, ast.ImportFrom): names = [node.module or ""]
            else: continue
            self.assertFalse(any(any(term in name.lower() for term in forbidden) for name in names))
if __name__ == "__main__": unittest.main()
