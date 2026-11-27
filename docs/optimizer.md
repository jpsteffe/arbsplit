# Horse-racing arbitrage optimizer (fixed odds + fixed pool snapshots)

This is the reference for `src/arbitrage_optimizer.py`. The web interface that calls it is in [app.md](app.md).

Two independent Python entry points optimize a **single race**:

- `maximize_guaranteed_profit(problem, *, time_limit=None)` finds the greatest worst-case net profit.
- `minimize_bets_with_arbitrage(problem, *, minimum_profit="0.01", tie_break="max_profit", time_limit=None)` finds the fewest **individual straight wagers** that meet the guaranteed-profit threshold.

Both accept JSON-compatible dictionaries and return JSON-compatible dictionaries. Both support fixed odds, pari-mutuel pool snapshots, or both together. **Ticket minimization, boxes, wheels, and multi-race bets are not implemented.**

**Important:** A pool snapshot is fixed throughout the entire optimization. The code does **not** account for the optimizer's own stakes entering a pari-mutuel pool, last-minute handle changes, actual dividends, breakage, minimum payouts, minus pools, scratches, dead heats, refunds, voids, or disqualifications. A theoretical positive result under the input snapshot is **not a guaranteed profit in real-world pari-mutuel betting**.

## Install and run

```bash
python -m pip install -r src/requirements.txt
PYTHONPATH=src python examples/example_arbitrage_usage.py
sh tests/run.sh
```

## Public API

```python
from arbitrage_optimizer import (
    maximize_guaranteed_profit,
    minimize_bets_with_arbitrage,
)

most_profit = maximize_guaranteed_profit(problem)
fewest_wagers = minimize_bets_with_arbitrage(
    problem,
    minimum_profit="0.01",  # minimum worst-case NET profit in dollars
    tie_break="max_profit",  # or "none"
)
```

The solver does not require spending the entire budget. `maximize_guaranteed_profit` allows zero stakes when no positive arbitrage exists; `minimize_bets_with_arbitrage` instead reports `status="infeasible"` if it cannot meet the requested positive profit threshold. The default min-bets tie-break is a **second optimization** that maximizes guaranteed profit only among portfolios with the already-minimal number of wagers.

## Full input schema: fixed-odds offers

The previous input format is unchanged:

```python
problem = {
    "horses": ["A", "B", "C"],
    "budget": "95.00",  # upper bound on total stakes
    "race_rules": {
        "place_pays_top": 2,  # default min(2, horse count)
        "show_pays_top": 3,   # default min(3, horse count)
    },
    "stake_rules": {
        "win": {
            "minimum": "1.00",
            "increment": "1.00",
            "increment_mode": "from_minimum",  # optional
            # "max_stake": "30.00",  # optional
        },
        "place": {"minimum": "1.00", "increment": "1.00"},
    },
    "book_limits": {"Book A": "50.00"},  # optional
    "offers": [
        {
            "id": "a-win-book-a",
            "book": "Book A",          # optional
            "market": "win",
            "selection": ["A"],
            "american_odds": 400,       # OR "decimal_odds": "5.00"
            # "minimum": "2.00",      # optional per-offer override
            # "increment": "1.00",    # optional per-offer override
            # "increment_mode": "multiples",
            # "max_stake": "20.00",   # optional per-offer cap
        },
        # ...
    ],
}
```

Fixed-odds offers must specify **exactly one** of `american_odds` or `decimal_odds`. American odds are integer-valued; decimal odds are exact strings and represent gross payout including stake per dollar wagered.

## New input schema: pari-mutuel pools

Add a `pools` dictionary and reference a pool from any offer using `pool_id` rather than fixed odds:

```python
problem = {
    "horses": ["A", "B", "C", "D"],
    "budget": "20.00",
    "race_rules": {"place_pays_top": 2, "show_pays_top": 3},
    "stake_rules": {"place": {"minimum": "1.00", "increment": "1.00"}},
    "pools": {
        "place-pool": {
            "market": "place",
            "gross_pool": "100.00",
            "takeout_rate": "0.15",
            "amounts": {
                "A": "20.00", "B": "30.00",
                "C": "10.00", "D": "40.00",
            },
        },
    },
    "offers": [
        {"id": "A-place", "market": "place", "selection": ["A"],
         "pool_id": "place-pool"},
        {"id": "B-place", "market": "place", "selection": ["B"],
         "pool_id": "place-pool"},
    ],
}
```

A pool-backed offer **must not** have an `american_odds` or `decimal_odds` field. Its `pool_id` must refer to a defined pool **with the same market**. You can mix fixed-odds and pool-backed offers in the same `offers` list. Pools are distinct by ID and by market, with each pool using its own gross pool, takeout, and handle distribution.

### Exact input requirements

- Monetary fields (`gross_pool`, `amounts`, stakes, budgets, limits, and profit thresholds) are decimal dollar **strings** with at most two decimal places. Floats are not accepted.
- `takeout_rate` is an exact decimal **string** in `[0, 1)`, such as `"0.15"` for 15%.
- `gross_pool` must equal the sum of **all** per-selection handle amounts. This is an intentional complete-snapshot requirement, not an estimate with unallocated handle.
- All possible winning selections in the pool must have **positive** handle. Missing or zero handles are rejected because zero-winner/refund settlements are outside scope.
- Pool-backed Place requires `place_pays_top == 2`; pool-backed Show requires `show_pays_top == 3`. Fixed-odds offers retain the existing customizable cutoff rules.
- Pool data may be identical across solver calls, but is never updated with the solver's selected stakes. This is a deliberate **price-taker approximation**, not a self-consistent final-pool calculation.

### Exotic-pool handle format

For Win, Place, and Show, `amounts` is a mapping from horse ID to dollars, as above.

For Exacta, Quinella, Trifecta, and Superfecta, use an **array of structured entries**, one for every possible winning combination:

```python
"pools": {
    "exacta-pool": {
        "market": "exacta",
        "gross_pool": "6.00",
        "takeout_rate": "0.10",
        "amounts": [
            {"selection": ["A", "B"], "amount": "1.00"},
            {"selection": ["A", "C"], "amount": "1.00"},
            {"selection": ["B", "A"], "amount": "1.00"},
            {"selection": ["B", "C"], "amount": "1.00"},
            {"selection": ["C", "A"], "amount": "1.00"},
            {"selection": ["C", "B"], "amount": "1.00"},
        ],
    },
}
```

This example requires a **three-horse** `horses` list. Ordered exotic combinations are distinct (`A-B` differs from `B-A`). Quinella combinations are unordered; the program normalizes them so reversed duplicate entries are rejected. All possible valid combinations must be provided. This conservative requirement can make large/exotic pool snapshots impractical, but prevents silently inventing payout rules for outcomes with zero winning handle.

## How the pool payouts are calculated

All calculations use exact `Fraction` arithmetic, retaining a separate theoretical gross payout ratio for each combination of scenario and offer.

Let `net_pool = gross_pool * (1 - takeout_rate)` and let `h[X]` be the pool's amount wagered on a selection.

**Place** (A and B finish top two):

```text
remaining = net_pool - h[A] - h[B]
A multiplier = 1 + remaining / (2 * h[A])
B multiplier = 1 + remaining / (2 * h[B])
```

For the four-horse input above, A's payout per dollar is:

| Finishing in top two | A Place gross multiplier |
|---|---:|
| A and B | 1.875x |
| A and C | 2.375x |
| A and D | 1.625x |

The order of the two horses does not change these multipliers.

**Show** (A, B, and C finish top three):

```text
remaining = net_pool - h[A] - h[B] - h[C]
A multiplier = 1 + remaining / (3 * h[A])
B multiplier = 1 + remaining / (3 * h[B])
C multiplier = 1 + remaining / (3 * h[C])
```

The order of the three horses does not matter, but their identities do.

**Win and straight exotic pools** use `net_pool / handle_on_winning_selection`. Supported pool markets are `win`, `place`, `show`, `exacta`, `quinella`, `trifecta`, and `superfecta`. Unmodeled special settlement practices are not inferred. A zero winning handle, a negative Place/Show distributable balance, or a net pool smaller than the winning handle in a single-winner market raises an explicit error rather than fabricating a dividend.

**Floor settlement:** For a winning stake of `x` **cents** at gross multiplier `numerator/denominator`, its payout is exactly:

```python
payout_cents = (numerator * x) // denominator
```

The per-wager floor-to-cent convention matches the previous implementation, but **is not necessarily how a specific track settles dividends**. Pool ratios with very large reduced fraction coefficients (> 1,000,000) are rejected to avoid numerical instability in integer-cent MILP constraints.

## Stake restrictions (unchanged)

Positive wagers must meet their per-offer or per-market minimum and increment, plus any maximum stake, book limit, and overall budget. A zero stake is always allowed.

For `$1` minimum and `$2` increment:

- `"from_minimum"` (default): `$0`, `$1`, `$3`, `$5`, ...
- `"multiples"`: `$0`, `$2`, `$4`, `$6`, ... (only amounts at least the minimum)

The optimizer does **not** choose ticket layouts or package several combinations into one ticket. `number_of_bets` counts only distinct positive-stake straight offers.

## Output and result verification

Successful fixed-odds results keep the original `payout_if_wins` field:

```json
{
  "id": "a-win",
  "book": null,
  "market": "win",
  "selection": ["A"],
  "odds": "+400",
  "stake": "20.00",
  "payout_if_wins": "100.00"
}
```

Pool-backed selected offers instead provide a range, because payout depends on other finishers:

```json
{
  "id": "C-place",
  "book": null,
  "market": "place",
  "selection": ["C"],
  "stake": "13.00",
  "pool_id": "place-2",
  "minimum_payout_if_wins": "19.50",
  "maximum_payout_if_wins": "26.00"
}
```

Both solutions still return `status`, `objective`, `budget`, `total_staked`, `minimum_payout`, `guaranteed_profit`, `number_of_bets`, `selected_bets`, `worst_case_finishes`, `scenarios_checked`, `all_scenarios_verified`, and `optimality_proven` as before. The min-bets solution also returns `minimum_profit_required` and `tie_break` when feasible.

The solver now caches integer-cent payout variables by `(offer_index, distinct_payout_ratio)`. Thus the exact same dividend for A Place when A-B vs. B-A finish is modeled by one variable, but A Place with C finishing alongside A receives its **own** payout variable. For every possible modeled finish, the constraint is `total_payout - total_staked >= guaranteed_profit`.

**Independent verification:** After HiGHS reports proven optimality, the code independently recalculates each selected offer's win condition and payout from the source fixed odds or pool data using rational and integer arithmetic. It rejects a result if a modeled dividend disagrees, an integer-cent payout is inconsistent, a stake rule is violated, or any outcome's net profit is below the claimed guarantee. Solver timeouts or lack of optimality proof produce `RuntimeError`, not an uncertified result.

## Deliberate limitations and integration notes

1. Pool data is a **fixed hypothetical snapshot**. The optimizer's own stakes are not incorporated into the pool or other participants' changing stakes; actual pool returns are not locked in.
2. Only distinct finishers, one race, and straight wagers are supported. No scratches, dead heats, disqualifications, refunds, voids, multi-race exotics, boxes, wheels, or ticket minimization.
3. The modeled payout formulas describe standard simplified pari-mutuel distribution, not universal track rules. Negative distributable profit, absent handle, minimum dividends, and unusual breakage rules are unsupported and explicitly rejected where detectable.
4. The 2-million-entry outcome-by-offer safety limit remains. Large exotic problems may require constraint generation or a different representation.
5. No fees, tax, exchange-rate, account limitation, bankroll funding transfer, odds availability verification, order execution, or bet placement.
6. Actual settlement rounding, takeout, allowable bet sizes, and pool rules must be verified for a specific venue before using real money.
7. Input is a plain Python dictionary, suitable for adapters to external systems. All returned monetary values are dollar strings; `selected_bets` and finish sequences are JSON-compatible.

## Tests

The original 17 regression tests remain intact. Additional tests cover exact Place ratios (including reverse order), Show variation, pool-backed Win and straight exotics, mixed fixed and pool offers, both public optimizers, min and increment modes, book limits, fractional-cent rounding, ratio reuse, incomplete or invalid pools, unsupported minus-pool conditions, and backwards compatibility.

```bash
PYTHONPATH=src python -m unittest -v tests/test_arbitrage_optimizer.py
```
