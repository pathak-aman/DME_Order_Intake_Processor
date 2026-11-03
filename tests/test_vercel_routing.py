"""Regression checks for Vercel's FastAPI framework routing configuration."""

import json
import os
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestVercelRouting(unittest.TestCase):
    def test_framework_entrypoint_and_no_legacy_api_functions(self):
        with open(os.path.join(ROOT, "main.py"), encoding="utf-8") as entrypoint:
            self.assertIn("from app.main import app", entrypoint.read())

        self.assertFalse(os.path.exists(os.path.join(ROOT, "api", "index.py")))
        self.assertFalse(os.path.exists(os.path.join(ROOT, "api", "[...path].py")))

    def test_api_routes_are_not_rewritten_to_python_files(self):
        with open(os.path.join(ROOT, "vercel.json"), encoding="utf-8") as config_file:
            config = json.load(config_file)

        for rule in config["rewrites"]:
            self.assertNotIn(".py", rule["destination"])
            self.assertFalse(rule["source"].startswith(("/api", "/auth", "/orders")))

        self.assertIn(
            {"source": "/", "destination": "/index.html"}, config["rewrites"]
        )
        self.assertIn(
            {"source": "/dashboard", "destination": "/dashboard.html"},
            config["rewrites"],
        )


if __name__ == "__main__":
    unittest.main()