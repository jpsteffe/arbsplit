"""Run: python -m unittest -v test_arbitrage_optimizer.py"""
from __future__ import annotations

import unittest

from arbitrage_optimizer import (
    maximize_guaranteed_profit,
    minimize_bets_with_arbitrage,
)


def basic_problem():
    return {
        "horses": ["A", "B", "C"],
        "budget": "95.00",
        "stake_rules": {
            "win": {"minimum": "1.00", "increment": "1.00"},
            "place": {"minimum": "1.00", "increment": "1.00"},
        },
        "offers": [
            {"id": "a-win", "market": "win", "selection": ["A"], "american_odds": 400},
            {"id": "a-place", "market": "place", "selection": ["A"], "american_odds": -400},
            {"id": "b-win", "market": "win", "selection": ["B"], "american_odds": 300},
            {"id": "b-place", "market": "place", "selection": ["B"], "american_odds": -400},
            {"id": "c-place", "market": "place", "selection": ["C"], "american_odds": 100},
        ],
    }


def two_horse_problem(odds=110, budget="200.00", minimum="1.00", increment="1.00"):
    return {
        "horses": ["A", "B"],
        "budget": budget,
        "stake_rules": {"win": {"minimum": minimum, "increment": increment}},
        "offers": [
            {"id": "a-win", "market": "win", "selection": ["A"], "american_odds": odds},
            {"id": "b-win", "market": "win", "selection": ["B"], "american_odds": odds},
        ],
    }


class TestOptimizer(unittest.TestCase):
    def test_known_win_place_solution(self):
        p = basic_problem()
        result = maximize_guaranteed_profit(p)
        self.assertEqual(result["status"], "optimal_arbitrage")
        self.assertEqual(result["total_staked"], "95.00")
        self.assertEqual(result["guaranteed_profit"], "5.00")
        self.assertEqual(result["number_of_bets"], 3)
        self.assertEqual({x["id"]: x["stake"] for x in result["selected_bets"]},
                         {"a-win": "20.00", "b-win": "25.00", "c-place": "50.00"})
        self.assertEqual(result["scenarios_checked"], 6)

    def test_minimum_bets_is_separate_objective(self):
        result = minimize_bets_with_arbitrage(basic_problem())
        self.assertEqual(result["number_of_bets"], 3)
        self.assertEqual(result["guaranteed_profit"], "5.00")

    def test_two_horse_symmetric_arbitrage(self):
        result = maximize_guaranteed_profit(two_horse_problem())
        self.assertEqual(result["guaranteed_profit"], "10.00")
        self.assertEqual(result["number_of_bets"], 2)
        self.assertEqual(result["scenarios_checked"], 2)
        self.assertEqual([b["stake"] for b in result["selected_bets"]],
                         ["100.00", "100.00"])

    def test_no_arbitrage(self):
        p = two_horse_problem(-110)
        result = maximize_guaranteed_profit(p)
        self.assertEqual(result["guaranteed_profit"], "0.00")
        self.assertEqual(result["status"], "no_arbitrage")
        infeasible = minimize_bets_with_arbitrage(p)
        self.assertEqual(infeasible["status"], "infeasible")

    def test_budget_is_maximum_not_required(self):
        p = two_horse_problem(budget="400.00")
        p["offers"][0]["max_stake"] = "1.00"
        p["offers"][1]["max_stake"] = "1.00"
        result = maximize_guaranteed_profit(p)
        self.assertEqual(result["total_staked"], "2.00")
        self.assertEqual(result["guaranteed_profit"], "0.10")

    def test_book_limits(self):
        p = two_horse_problem(budget="200.00")
        p["offers"][0]["book"] = "Book-A"
        p["offers"][1]["book"] = "Book-B"
        p["book_limits"] = {"Book-A": "10.00", "Book-B": "10.00"}
        result = maximize_guaranteed_profit(p)
        self.assertEqual(result["total_staked"], "20.00")
        self.assertEqual(result["guaranteed_profit"], "1.00")

    def test_cent_level_floor_discards_fractional_cent_arb(self):
        p = two_horse_problem(budget="2.00")
        for o in p["offers"]:
            del o["american_odds"]
            o["decimal_odds"] = "2.001"  # $1 winning payout rounds DOWN to $2.00
        result = maximize_guaranteed_profit(p)
        self.assertEqual(result["guaranteed_profit"], "0.00")
        self.assertEqual(minimize_bets_with_arbitrage(p)["status"], "infeasible")

    def test_minimum_and_increments_from_minimum(self):
        p = two_horse_problem(budget="8.00", minimum="1.00", increment="2.00")
        result = maximize_guaranteed_profit(p)
        self.assertEqual(result["total_staked"], "6.00")
        self.assertEqual(result["guaranteed_profit"], "0.30")
        self.assertEqual([x["stake"] for x in result["selected_bets"]],
                         ["3.00", "3.00"])

    def test_minimum_and_increments_multiples_of_increment(self):
        p = two_horse_problem(budget="8.00", minimum="1.00", increment="2.00")
        p["stake_rules"]["win"]["increment_mode"] = "multiples"
        result = maximize_guaranteed_profit(p)
        self.assertEqual(result["total_staked"], "8.00")
        self.assertEqual(result["guaranteed_profit"], "0.40")
        self.assertEqual([x["stake"] for x in result["selected_bets"]],
                         ["4.00", "4.00"])

    def test_positive_profit_threshold(self):
        p = two_horse_problem(budget="20.00")
        self.assertEqual(minimize_bets_with_arbitrage(p, minimum_profit="2.00")["status"],
                         "infeasible")
        good = minimize_bets_with_arbitrage(p, minimum_profit="1.00")
        self.assertEqual(good["guaranteed_profit"], "1.00")

    def test_objectives_produce_different_portfolios(self):
        p = {
            "horses": ["A", "B", "C"], "budget": "30.00",
            "stake_rules": {
                "win": {"minimum": "1.00", "increment": "1.00"},
                "place": {"minimum": "1.00", "increment": "1.00"},
            },
            "offers": [
                {"id": "Awin", "market": "win", "selection": ["A"], "american_odds": 600},
                {"id": "Aplace", "market": "place", "selection": ["A"], "american_odds": 200},
                {"id": "Bwin", "market": "win", "selection": ["B"], "american_odds": 200},
                {"id": "Bplace", "market": "place", "selection": ["B"], "american_odds": -200},
                {"id": "Cwin", "market": "win", "selection": ["C"], "american_odds": 300},
                {"id": "Cplace", "market": "place", "selection": ["C"], "american_odds": -150},
            ],
        }
        maximum = maximize_guaranteed_profit(p)
        fewest = minimize_bets_with_arbitrage(p)
        self.assertEqual(maximum["number_of_bets"], 6)
        self.assertEqual(maximum["guaranteed_profit"], "10.16")
        self.assertEqual(fewest["number_of_bets"], 2)
        self.assertEqual(fewest["guaranteed_profit"], "2.00")
        self.assertEqual({b["id"] for b in fewest["selected_bets"]},
                         {"Aplace", "Cplace"})

    def test_tie_break_none(self):
        result = minimize_bets_with_arbitrage(basic_problem(), tie_break="none")
        self.assertEqual(result["number_of_bets"], 3)
        self.assertEqual(result["tie_break"], "none")

    def test_exotics_win_place_show(self):
        p = {
            "horses": ["A", "B", "C", "D"],
            "budget": "40.00",
            "stake_rules": {"show": {"minimum": "10.00", "increment": "10.00"}},
            "offers": [
                {"id": f"show-{h}", "market": "show", "selection": [h],
                 "american_odds": -200}
                for h in ["A", "B", "C", "D"]
            ],
        }
        result = maximize_guaranteed_profit(p)
        self.assertEqual(result["guaranteed_profit"], "5.00")
        self.assertEqual(result["number_of_bets"], 4)
        self.assertEqual(result["scenarios_checked"], 24)
        self.assertEqual(minimize_bets_with_arbitrage(p)["number_of_bets"], 4)

    def test_exacta_and_quinella(self):
        p = {
            "horses": ["A", "B", "C"],
            "budget": "6.00",
            "stake_rules": {
                "exacta": {"minimum": "1.00", "increment": "1.00"},
                "quinella": {"minimum": "1.00", "increment": "1.00"},
            },
            "offers": ([
                {"id": f"ex-{a}{b}", "market": "exacta", "selection": [a,b],
                 "american_odds": 1000}
                for a in "ABC" for b in "ABC" if a != b
            ] + [
                {"id": "q-ab", "market": "quinella", "selection": ["A", "B"],
                 "american_odds": 100},
            ]),
        }
        result = maximize_guaranteed_profit(p)
        self.assertEqual(result["scenarios_checked"], 6)
        self.assertTrue(result["all_scenarios_verified"])
        self.assertGreater(float(result["guaranteed_profit"]), 0)

    def test_race_rules_override_place_cutoff(self):
        p = basic_problem()
        p["race_rules"] = {"place_pays_top": 1, "show_pays_top": 3}
        result = maximize_guaranteed_profit(p)
        self.assertEqual(result["guaranteed_profit"], "5.00")  # Still covers every winner
        self.assertEqual(result["scenarios_checked"], 3)  # place now only depends on first

    def test_reject_float_money(self):
        p = basic_problem()
        p["budget"] = 95.00
        with self.assertRaisesRegex(ValueError, "not float"):
            maximize_guaranteed_profit(p)

    def test_reject_invalid_selection(self):
        p = basic_problem()
        p["offers"][0]["selection"] = ["BAD"]
        with self.assertRaisesRegex(ValueError, "invalid selection"):
            maximize_guaranteed_profit(p)


def place_pool_problem():
    """The four-horse example from the pari-mutuel extension specification."""
    return {
        "horses": ["A", "B", "C", "D"],
        "budget": "20.00",
        "pools": {
            "place-pool": {
                "market": "place", "gross_pool": "100.00",
                "takeout_rate": "0.15",
                "amounts": {"A": "20.00", "B": "30.00",
                            "C": "10.00", "D": "40.00"},
            },
        },
        "stake_rules": {"place": {"minimum": "1.00", "increment": "1.00"}},
        "offers": [
            {"id": f"place-{h}", "market": "place", "selection": [h],
             "pool_id": "place-pool"}
            for h in "ABCD"
        ],
    }


def mixed_pool_problem():
    """Three-horse example with a variable Place price and fixed Win odds."""
    return {
        "horses": ["A", "B", "C"], "budget": "20.00",
        "pools": {"p": {"market": "place", "gross_pool": "100.00",
                        "takeout_rate": "0.10",
                        "amounts": {"A": "30.00", "B": "50.00", "C": "20.00"}}},
        "stake_rules": {"win": {"minimum": "1.00", "increment": "1.00"},
                        "place": {"minimum": "1.00", "increment": "1.00"}},
        "offers": [
            {"id": "A-win", "market": "win", "selection": ["A"],
             "american_odds": 900, "book": "fixed"},
            {"id": "B-win", "market": "win", "selection": ["B"],
             "american_odds": 900, "book": "fixed"},
            {"id": "C-place", "market": "place", "selection": ["C"],
             "pool_id": "p", "book": "pool"},
        ],
    }


class TestParimutuel(unittest.TestCase):
    def test_place_exact_multipliers_and_order_invariance(self):
        from fractions import Fraction
        from arbitrage_optimizer import _build_problem, _MILPModel
        p = _build_problem(place_pool_problem())
        i = next(i for i, o in enumerate(p.offers) if o.id == "place-A")
        ratios = {order: p.payout_ratios[s, i]
                  for s, order in enumerate(p.outcomes)}
        for opponent, expected in [
            ("B", Fraction(15, 8)),
            ("C", Fraction(19, 8)),
            ("D", Fraction(13, 8)),
        ]:
            self.assertEqual(ratios[("A", opponent)], expected)
            self.assertEqual(ratios[(opponent, "A")], expected)
        self.assertIsNone(ratios[("B", "C")])
        model = _MILPModel(p)
        self.assertEqual(len({ratio for (offer_i, ratio) in model.q_by_key if offer_i == i}), 3)
        self.assertEqual(len(model.q_by_key), 12)  # 4 offers x 3 partners

    def test_show_variable_payouts_and_permutations(self):
        from fractions import Fraction
        from arbitrage_optimizer import _build_problem
        d = {
            "horses": ["A", "B", "C", "D"], "budget": "10.00",
            "pools": {"s": {"market": "show", "gross_pool": "100.00",
                            "takeout_rate": "0.15",
                            "amounts": {"A": "15.00", "B": "20.00",
                                        "C": "25.00", "D": "40.00"}}},
            "stake_rules": {"show": {"minimum": "1.00", "increment": "1.00"}},
            "offers": [{"id": f"show-{h}", "market": "show", "selection": [h],
                        "pool_id": "s"} for h in "ABCD"],
        }
        p = _build_problem(d)
        i = 0  # A Show
        ratios = {order: p.payout_ratios[s, i] for s, order in enumerate(p.outcomes)}
        self.assertEqual(ratios[("A", "B", "C")], Fraction(14, 9))
        self.assertEqual(ratios[("A", "B", "D")], Fraction(11, 9))
        self.assertEqual(ratios[("B", "A", "C")], Fraction(14, 9))
        self.assertEqual(ratios[("D", "B", "A")], Fraction(11, 9))
        self.assertIsNone(ratios[("B", "C", "D")])
        self.assertEqual(maximize_guaranteed_profit(d)["scenarios_checked"], 24)

    def test_mixed_fixed_and_pool_both_solvers_and_book_limits(self):
        d = mixed_pool_problem()
        d["book_limits"] = {"fixed": "5.00", "pool": "16.00"}
        most = maximize_guaranteed_profit(d)
        fewest = minimize_bets_with_arbitrage(d)
        for result in [most, fewest]:
            self.assertEqual(result["status"], "optimal_arbitrage")
            self.assertTrue(result["all_scenarios_verified"])
            self.assertGreater(float(result["guaranteed_profit"]), 0)
            self.assertLessEqual(float(result["total_staked"]), 20)
            self.assertEqual(result["number_of_bets"], 3)
            pooled = next(b for b in result["selected_bets"] if b["id"] == "C-place")
            self.assertEqual(pooled["pool_id"], "p")
            self.assertNotIn("payout_if_wins", pooled)
            self.assertLess(float(pooled["minimum_payout_if_wins"]),
                            float(pooled["maximum_payout_if_wins"]))
            self.assertTrue(all("payout_if_wins" in b for b in result["selected_bets"]
                                if b["market"] == "win"))
            self.assertLessEqual(sum(float(b["stake"]) for b in result["selected_bets"]
                                     if b["book"] == "fixed"), 5)
            self.assertLessEqual(sum(float(b["stake"]) for b in result["selected_bets"]
                                     if b["book"] == "pool"), 16)
        self.assertEqual(fewest["minimum_profit_required"], "0.01")

    def test_pool_rounding_with_cent_stakes(self):
        d = mixed_pool_problem()
        d["budget"] = "0.09"
        d["stake_rules"] = {
            "win": {"minimum": "0.01", "increment": "0.01"},
            "place": {"minimum": "0.07", "increment": "0.01"},
        }
        d["offers"][0]["american_odds"] = 10000
        d["offers"][1]["american_odds"] = 10000
        d["offers"][2]["max_stake"] = "0.07"
        result = minimize_bets_with_arbitrage(d)
        self.assertEqual(result["status"], "optimal_arbitrage")
        self.assertEqual(result["total_staked"], "0.09")
        self.assertEqual(result["guaranteed_profit"], "0.01")
        pooled = next(b for b in result["selected_bets"] if b["id"] == "C-place")
        self.assertEqual(pooled["stake"], "0.07")
        self.assertEqual(pooled["minimum_payout_if_wins"], "0.10")
        self.assertEqual(pooled["maximum_payout_if_wins"], "0.14")
        self.assertEqual(maximize_guaranteed_profit(d)["guaranteed_profit"], "0.01")

    def test_pool_and_fixed_increment_modes_preserved(self):
        d = mixed_pool_problem()
        d["stake_rules"]["win"] = {"minimum": "1.00", "increment": "2.00",
                                     "increment_mode": "multiples"}
        d["stake_rules"]["place"] = {"minimum": "1.00", "increment": "2.00",
                                       "increment_mode": "from_minimum"}
        result = maximize_guaranteed_profit(d)
        self.assertEqual(result["status"], "optimal_arbitrage")
        for item in result["selected_bets"]:
            cents = round(float(item["stake"]) * 100)
            if item["market"] == "win":
                self.assertEqual(cents % 200, 0)
            else:
                self.assertEqual((cents - 100) % 200, 0)

    def test_pool_win_and_all_straight_exotics(self):
        from arbitrage_optimizer import _build_problem
        from itertools import permutations, combinations
        from fractions import Fraction
        for market in ["win", "exacta", "quinella", "trifecta", "superfecta"]:
            with self.subTest(market=market):
                horses = ["A", "B", "C", "D"]
                depth = {"win": 1, "exacta": 2, "quinella": 2,
                         "trifecta": 3, "superfecta": 4}[market]
                combos = (list(combinations(horses, 2)) if market == "quinella" else
                          list(permutations(horses, depth)))
                n = len(combos)
                amounts = ({h: "1.00" for h in horses} if market == "win" else
                           [{"selection": list(c), "amount": "1.00"} for c in combos])
                d = {"horses": horses, "budget": "2.00",
                     "stake_rules": {market: {"minimum": "1.00", "increment": "1.00"}},
                     "pools": {"ex": {"market": market, "gross_pool": f"{n}.00",
                                      "takeout_rate": "0.10", "amounts": amounts}},
                     "offers": [{"id": "offer", "selection": list(combos[0]),
                                 "market": market, "pool_id": "ex"}]}
                p = _build_problem(d)
                self.assertEqual({r for row in p.payout_ratios for r in row
                                  if r is not None}, {Fraction(9*n, 10)})
                res = maximize_guaranteed_profit(d)
                self.assertEqual(res["status"], "no_arbitrage")
                self.assertTrue(res["all_scenarios_verified"])

    def test_milp_matches_exhaustive_small_mixed_problem(self):
        """Cross-check both objectives against every feasible cent allocation."""
        from arbitrage_optimizer import _build_problem, _offer_wins, _offer_ratio
        d = mixed_pool_problem()
        d["budget"] = "0.16"
        d["stake_rules"] = {
            "win": {"minimum": "0.01", "increment": "0.01"},
            "place": {"minimum": "0.01", "increment": "0.01"},
        }
        p = _build_problem(d)
        exhaustive = []
        for a in range(17):
            for b in range(17 - a):
                for c in range(17 - a - b):
                    stakes = [a, b, c]
                    spent = sum(stakes)
                    nets = []
                    for order in p.outcomes:
                        gross = sum(
                            _offer_ratio(o, p.pools, order).numerator * st
                            // _offer_ratio(o, p.pools, order).denominator
                            for o, st in zip(p.offers, stakes)
                            if st and _offer_wins(o, order, p.place_pays_top, p.show_pays_top)
                        )
                        nets.append(gross - spent)
                    exhaustive.append((min(nets), sum(st > 0 for st in stakes)))
        best_profit = max(profit for profit, count in exhaustive)
        eligible = [(profit, count) for profit, count in exhaustive if profit >= 1]
        minimum_count = min(count for profit, count in eligible)
        best_tiebreak_profit = max(profit for profit, count in eligible
                                   if count == minimum_count)

        most = maximize_guaranteed_profit(d)
        fewest = minimize_bets_with_arbitrage(d)
        self.assertEqual(int(round(100 * float(most["guaranteed_profit"]))), best_profit)
        self.assertEqual(fewest["number_of_bets"], minimum_count)
        self.assertEqual(int(round(100 * float(fewest["guaranteed_profit"]))),
                         best_tiebreak_profit)

    def test_invalid_pool_data_rejected(self):
        import copy
        cases = [
            (lambda x: x["pools"]["place-pool"].update(gross_pool="100.01"), "does not equal"),
            (lambda x: x["pools"]["place-pool"].update(takeout_rate="1.00"), "takeout_rate"),
            (lambda x: x["pools"]["place-pool"].update(takeout_rate=0.15), "takeout_rate"),
            (lambda x: x["pools"]["place-pool"]["amounts"].pop("B"), "incomplete"),
            (lambda x: x["pools"]["place-pool"]["amounts"].update(B="0.00"), "positive"),
            (lambda x: x["pools"]["place-pool"].update(market="show"), "is for show, not place"),
            (lambda x: x["offers"][0].update(pool_id="missing"), "unknown pool_id"),
            (lambda x: x["offers"][0].update(american_odds=100), "must not specify fixed odds"),
            (lambda x: x["race_rules"].update(place_pays_top=1), "requires standard"),
        ]
        for mutate, expected in cases:
            with self.subTest(expected=expected):
                d = copy.deepcopy(place_pool_problem())
                d.setdefault("race_rules", {})
                mutate(d)
                with self.assertRaisesRegex(ValueError, expected):
                    maximize_guaranteed_profit(d)

    def test_negative_distributable_profit_rejected(self):
        d = {
            "horses": ["A", "B", "C", "D"], "budget": "1.00",
            "stake_rules": {"show": {"minimum": "1.00", "increment": "1.00"}},
            "pools": {"s": {"market": "show", "gross_pool": "100.00",
                            "takeout_rate": "0.15",
                            "amounts": {"A": "30.00", "B": "30.00",
                                        "C": "30.00", "D": "10.00"}}},
            "offers": [{"id": "A-show", "market": "show", "selection": ["A"],
                        "pool_id": "s"}],
        }
        with self.assertRaisesRegex(ValueError, "negative distributable profit"):
            maximize_guaranteed_profit(d)

    def test_pool_reference_wrong_market(self):
        d = place_pool_problem()
        d["offers"][0]["market"] = "win"
        with self.assertRaisesRegex(ValueError, "is for place, not win"):
            maximize_guaranteed_profit(d)

    def test_missing_odds_on_fixed_offer_still_rejected(self):
        d = mixed_pool_problem()
        d["offers"][0].pop("american_odds")
        with self.assertRaisesRegex(ValueError, "exactly one"):
            maximize_guaranteed_profit(d)

    def test_reject_exotic_incomplete_amounts(self):
        d = {"horses": ["A", "B", "C"], "budget": "1.00",
             "stake_rules": {"exacta": {"minimum": "1.00", "increment": "1.00"}},
             "pools": {"e": {"market": "exacta", "gross_pool": "1.00",
                              "takeout_rate": "0.10",
                              "amounts": [{"selection": ["A", "B"], "amount": "1.00"}]}},
             "offers": [{"id": "ab", "market": "exacta", "selection": ["A", "B"],
                         "pool_id": "e"}]}
        with self.assertRaisesRegex(ValueError, "incomplete pool amounts"):
            maximize_guaranteed_profit(d)


if __name__ == "__main__":
    unittest.main()
