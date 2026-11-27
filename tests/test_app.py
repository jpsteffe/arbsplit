"""Run: python -m unittest -v test_app.py"""

from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from app import app
from test_arbitrage_optimizer import basic_problem, mixed_pool_problem


class TestApp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_index_and_static_assets(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Prairie Meadows", response.text)
        self.assertIn("/static/app.js", response.text)
        self.assertEqual(self.client.get("/static/styles.css").status_code, 200)
        tracks = self.client.get("/static/tracks.js")
        self.assertEqual(tracks.status_code, 200)
        self.assertIn("Altoona, Iowa", tracks.text)
        self.assertIn('trifecta: "0.50"', tracks.text)
        self.assertIn('superfecta: "0.10"', tracks.text)

    def test_single_endpoint_both_modes_legacy_example(self):
        r = self.client.post("/api/calculate", json={"problem": basic_problem()})
        self.assertEqual(r.status_code, 200, r.text)
        data = r.json()["results"]
        self.assertEqual(set(data), {"max_profit", "min_bets"})
        self.assertEqual(data["max_profit"]["guaranteed_profit"], "5.00")
        self.assertEqual(data["min_bets"]["number_of_bets"], 3)
        self.assertTrue(data["max_profit"]["optimality_proven"])

    def test_single_mode_min_bets(self):
        r = self.client.post("/api/calculate", json={
            "problem": basic_problem(), "mode": "min_bets", "minimum_profit": "1.00"
        })
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(list(r.json()["results"]), ["min_bets"])

    def test_pool_backed_result(self):
        r = self.client.post("/api/calculate", json={
            "problem": mixed_pool_problem(), "mode": "max_profit"
        })
        self.assertEqual(r.status_code, 200, r.text)
        data = r.json()["results"]["max_profit"]
        self.assertTrue(data["all_scenarios_verified"])
        self.assertEqual(data["status"], "optimal_arbitrage")
        self.assertTrue(any("pool_id" in wager for wager in data["selected_bets"]))

    def test_validation_error(self):
        bad = basic_problem()
        bad["horses"] = ["A", "A", "C"]
        r = self.client.post("/api/calculate", json={"problem": bad})
        self.assertEqual(r.status_code, 422)
        self.assertIn("distinct", r.json()["detail"])

    def test_schema_prevents_unbounded_timeout(self):
        r = self.client.post("/api/calculate", json={
            "problem": basic_problem(), "time_limit": 1000
        })
        self.assertEqual(r.status_code, 422)

    def test_only_post_calculates(self):
        r = self.client.get("/api/calculate")
        self.assertEqual(r.status_code, 405)


if __name__ == "__main__":
    unittest.main()
