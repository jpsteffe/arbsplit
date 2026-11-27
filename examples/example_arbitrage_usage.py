"""Example: unchanged fixed odds, plus a fixed-snapshot pari-mutuel pool.

Run: python example_arbitrage_usage.py
All payouts here are hypothetical; the optimizer does not model the impact of
our stake on a pool, final handle changes, breakage, or race exceptions.
"""

import json
from fractions import Fraction

from arbitrage_optimizer import (
    maximize_guaranteed_profit,
    minimize_bets_with_arbitrage,
)

# Original fixed-odds input, unchanged.
fixed_problem = {
    "horses": ["A", "B", "C"],
    "budget": "95.00",
    "race_rules": {"place_pays_top": 2, "show_pays_top": 3},
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

# New: a fixed snapshot of a four-horse Place pool.
place_pool = {
    "market": "place",
    "gross_pool": "100.00",
    "takeout_rate": "0.15",
    "amounts": {"A": "20.00", "B": "30.00", "C": "10.00", "D": "40.00"},
}
place_problem = {
    "horses": ["A", "B", "C", "D"],
    "budget": "20.00",
    "pools": {"place-pool": place_pool},
    "stake_rules": {"place": {"minimum": "1.00", "increment": "1.00"}},
    "offers": [
        {"id": f"place-{horse}", "market": "place",
         "selection": [horse], "pool_id": "place-pool"}
        for horse in "ABCD"
    ],
}

# A profitable mixed problem where A/B have fixed Win odds while C's Place
# price depends on which of A/B finishes alongside C in the top two.
mixed_problem = {
    "horses": ["A", "B", "C"],
    "budget": "20.00",
    "pools": {
        "place-2": {
            "market": "place", "gross_pool": "100.00", "takeout_rate": "0.10",
            "amounts": {"A": "30.00", "B": "50.00", "C": "20.00"},
        }
    },
    "stake_rules": {
        "win": {"minimum": "1.00", "increment": "1.00"},
        "place": {"minimum": "1.00", "increment": "1.00"},
    },
    "offers": [
        {"id": "A-win", "market": "win", "selection": ["A"],
         "american_odds": 900},
        {"id": "B-win", "market": "win", "selection": ["B"],
         "american_odds": 900},
        {"id": "C-place", "market": "place", "selection": ["C"],
         "pool_id": "place-2"},
    ],
}


def run_both(title, problem):
    print("\n" + title)
    for name, result in (
        ("MAX GUARANTEED PROFIT", maximize_guaranteed_profit(problem)),
        ("MINIMUM NUMBER OF BETS", minimize_bets_with_arbitrage(problem)),
    ):
        print(name)
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    run_both("FIXED-ODDS CASE (BACKWARD COMPATIBLE)", fixed_problem)

    # Exact theoretical Place prices for A: partner affects the remaining net
    # pool, even though A finishes in the paid places in every example.
    net_cents = Fraction(8500)
    a_handle = 2000
    handles = {"B": 3000, "C": 1000, "D": 4000}
    print("\nFOUR-HORSE PLACE-POOL SNAPSHOT: A's theoretical dividend")
    for partner, partner_handle in handles.items():
        multiplier = 1 + (net_cents - a_handle - partner_handle) / (2 * a_handle)
        print(f"A and {partner} in the top two: {float(multiplier):.3f}x total payout")
    run_both("FOUR-HORSE PLACE-POOL EXAMPLE", place_problem)
    run_both("MIXED FIXED-ODDS + PARI-MUTUEL EXAMPLE", mixed_problem)
