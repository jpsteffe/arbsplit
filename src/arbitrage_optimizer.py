"""Single-race fixed-odds and pari-mutuel-pool arbitrage optimization.

Public entry points (unchanged):
    maximize_guaranteed_profit(problem, *, time_limit=None)
    minimize_bets_with_arbitrage(problem, *, minimum_profit='0.01',
                                 tie_break='max_profit', time_limit=None)

Both accept and return JSON-compatible dictionaries. Money uses decimal dollar
strings on input/output and integer cents internally. Pool arithmetic is exact
(Fraction); winning payouts are floored to cents, separately for each wager.

Only one race with distinct finishers is modeled. Pool data is treated as a
fixed snapshot; the model deliberately does not account for new wagers changing
pool prices, final handle changes, breakage/minimum dividends, dead heats,
scratches, refunds, or voids. Thus a result is NOT a real pari-mutuel guarantee.

A selected offer is one straight wager; ticket packaging is not implemented.
Requires scipy and numpy. Solves with scipy.optimize.milp (HiGHS).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from itertools import combinations, permutations
from math import isfinite
from typing import Any

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import coo_array


_MARKETS = {"win": 1, "place": 1, "show": 1, "exacta": 2,
            "quinella": 2, "trifecta": 3, "superfecta": 4}
_SINGLE = {"win", "place", "show"}
# Coefficient limit is deliberate. Integer floor constraints with much larger
# coefficients cannot be trusted to remain exact in a floating-point MILP solver.
_MAX_COEFFICIENT = 1_000_000
_MAX_MATRIX_ELEMENTS = 2_000_000


@dataclass(frozen=True)
class _Pool:
    id: str
    market: str
    gross_cents: int
    takeout_rate: Fraction
    net_cents: Fraction
    amounts_cents: dict[tuple[str, ...], int]


@dataclass(frozen=True)
class _Offer:
    id: str
    book: str | None
    market: str
    selection: tuple[str, ...]
    displayed_odds: str | None
    payout_ratio: Fraction | None
    pool_id: str | None
    minimum_cents: int
    increment_cents: int
    increment_mode: str
    maximum_cents: int


@dataclass(frozen=True)
class _Problem:
    horses: tuple[str, ...]
    budget_cents: int
    offers: tuple[_Offer, ...]
    outcomes: tuple[tuple[str, ...], ...]
    wins: np.ndarray  # bool, outcome x offer; retained for compatibility
    payout_ratios: np.ndarray  # Fraction or None, outcome x offer
    pools: dict[str, _Pool]
    book_limits_cents: dict[str, int]
    place_pays_top: int
    show_pays_top: int


def _money_cents(value: Any, *, field: str, allow_zero: bool = False) -> int:
    """Parse decimal dollar strings to exact integer cents, rejecting floats."""
    if isinstance(value, (bool, float)):
        raise ValueError(f"{field} must be a decimal string (e.g. '2.50'), not float")
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field} must be a decimal dollar amount") from exc
    if not amount.is_finite() or amount != amount.quantize(Decimal("0.01")):
        raise ValueError(f"{field} must be finite and have at most 2 decimal places")
    cents = int(amount * 100)
    if cents < 0 or (cents == 0 and not allow_zero):
        raise ValueError(f"{field} must be {'nonnegative' if allow_zero else 'positive'}")
    return cents


def _money(cents: int) -> str:
    return f"{cents // 100}.{cents % 100:02d}"


def _require_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be a dictionary")
    return value


def _check_ratio(ratio: Fraction, label: str) -> Fraction:
    if ratio <= 0:
        raise ValueError(f"{label}: payout ratio must be positive")
    if (ratio.numerator > _MAX_COEFFICIENT or
            ratio.denominator > _MAX_COEFFICIENT):
        raise ValueError(
            f"{label}: payout fraction {ratio} has coefficients too large "
            "for stable integer-cent MILP constraints; simplify pool inputs "
            "or use a different settlement/optimization implementation")
    return ratio


def _odds_ratio(offer: Mapping[str, Any], label: str) -> tuple[Fraction, str]:
    has_american = "american_odds" in offer
    has_decimal = "decimal_odds" in offer
    if has_american == has_decimal:
        raise ValueError(f"{label}: supply exactly one of american_odds or decimal_odds")
    if has_american:
        odds = offer["american_odds"]
        if isinstance(odds, (bool, float)):
            raise ValueError(f"{label}: american_odds must be an integer")
        try:
            odds_int = int(odds)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{label}: american_odds must be an integer") from exc
        if str(odds).strip() not in {str(odds_int), f"+{odds_int}"}:
            raise ValueError(f"{label}: american_odds must be an integer")
        if odds_int == 0:
            raise ValueError(f"{label}: american_odds cannot be zero")
        ratio = (Fraction(100 + odds_int, 100) if odds_int > 0 else
                 Fraction(abs(odds_int) + 100, abs(odds_int)))
        display = f"{odds_int:+d}"
    else:
        odds = offer["decimal_odds"]
        if isinstance(odds, (float, bool)):
            raise ValueError(f"{label}: decimal_odds must be a string, not float")
        try:
            d = Decimal(str(odds))
        except (InvalidOperation, ValueError) as exc:
            raise ValueError(f"{label}: invalid decimal_odds") from exc
        if not d.is_finite() or d <= 1:
            raise ValueError(f"{label}: decimal_odds must be > 1.00")
        ratio = Fraction(d)
        display = f"{d} decimal"
    return _check_ratio(ratio, label), display


def _parse_takeout(value: Any, label: str) -> Fraction:
    if isinstance(value, (bool, float)):
        raise ValueError(f"{label}: takeout_rate must be an exact decimal string")
    try:
        d = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{label}: invalid takeout_rate") from exc
    if not d.is_finite() or not (0 <= d < 1):
        raise ValueError(f"{label}: takeout_rate must be >= 0 and < 1")
    return Fraction(d)


def _key_for_selection(market: str, selection: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(sorted(selection)) if market == "quinella" else selection


def _expected_pool_keys(market: str, horses: tuple[str, ...]):
    if market in _SINGLE:
        return ((h,) for h in horses)
    if market == "quinella":
        return (tuple(sorted(c)) for c in combinations(horses, 2))
    return permutations(horses, _MARKETS[market])


def _parse_pools(raw: Any, horses: tuple[str, ...], *,
                 place_top: int, show_top: int) -> dict[str, _Pool]:
    pools_raw = _require_mapping(raw, "pools")
    result: dict[str, _Pool] = {}
    for pool_id, raw_pool in pools_raw.items():
        if not isinstance(pool_id, str) or not pool_id.strip():
            raise ValueError("pools: pool IDs must be nonempty strings")
        data = _require_mapping(raw_pool, f"pools[{pool_id}]")
        market = data.get("market")
        if not isinstance(market, str) or market.lower() not in _MARKETS:
            raise ValueError(f"pools[{pool_id}]: unsupported market {market!r}")
        market = market.lower()
        if _MARKETS[market] > len(horses):
            raise ValueError(f"pools[{pool_id}]: too few horses for {market}")
        # The specified split-the-remaining-pool formula only models ordinary
        # top-2 Place and top-3 Show; alternate small-field settlement differs.
        if (market == "place" and place_top != 2) or (market == "show" and show_top != 3):
            raise ValueError(
                f"pools[{pool_id}]: pool-backed {market} requires standard "
                "place_pays_top=2 and show_pays_top=3, respectively")
        gross = _money_cents(data.get("gross_pool"), field=f"pools[{pool_id}].gross_pool")
        takeout = _parse_takeout(data.get("takeout_rate"), f"pools[{pool_id}]")
        amounts_raw = data.get("amounts")
        amounts: dict[tuple[str, ...], int] = {}
        if market in _SINGLE:
            entries = _require_mapping(amounts_raw, f"pools[{pool_id}].amounts")
            for horse, amount_raw in entries.items():
                if not isinstance(horse, str) or horse not in horses:
                    raise ValueError(f"pools[{pool_id}]: unknown horse {horse!r} in amounts")
                amounts[(horse,)] = _money_cents(
                    amount_raw, field=f"pools[{pool_id}].amounts[{horse}]")
        else:
            # Exotic pools use structured entries to avoid ambiguous selection
            # strings (and to represent quinella's unordered pair cleanly).
            if not isinstance(amounts_raw, list):
                raise ValueError(
                    f"pools[{pool_id}].amounts must be a list of "
                    "{'selection': [...], 'amount': '...'} entries for exotic pools")
            for j, entry_raw in enumerate(amounts_raw):
                entry = _require_mapping(entry_raw, f"pools[{pool_id}].amounts[{j}]")
                selection = entry.get("selection")
                if (not isinstance(selection, (list, tuple)) or
                        len(selection) != _MARKETS[market] or
                        not all(isinstance(h, str) and h in horses for h in selection) or
                        len(set(selection)) != len(selection)):
                    raise ValueError(f"pools[{pool_id}].amounts[{j}]: invalid selection")
                key = _key_for_selection(market, tuple(selection))
                if key in amounts:
                    raise ValueError(f"pools[{pool_id}]: duplicate pool selection {key!r}")
                amounts[key] = _money_cents(
                    entry.get("amount"), field=f"pools[{pool_id}].amounts[{j}].amount")
        # Require a complete pool snapshot, including all potential winning
        # combinations, so zero-winning-handle/refund scenarios are not guessed.
        expected = set(_expected_pool_keys(market, horses))
        if set(amounts) != expected:
            missing = expected - set(amounts)
            extras = set(amounts) - expected
            raise ValueError(
                f"pools[{pool_id}]: incomplete pool amounts "
                f"({len(missing)} missing, {len(extras)} extra); "
                f"example missing selection: {next(iter(sorted(missing)), None)!r}")
        if sum(amounts.values()) != gross:
            raise ValueError(
                f"pools[{pool_id}]: amounts total {_money(sum(amounts.values()))} "
                f"does not equal gross_pool {_money(gross)}")
        net = Fraction(gross) * (1 - takeout)
        if net <= 0:
            raise ValueError(f"pools[{pool_id}]: nonpositive net pool")
        result[pool_id] = _Pool(pool_id, market, gross, takeout, net, amounts)
    return result


def _pool_multiplier(pool: _Pool, selection: tuple[str, ...],
                     order: tuple[str, ...]) -> Fraction:
    """Exact gross payout per $1 for a winning offer, using a FIXED pool."""
    if pool.market in {"place", "show"}:
        paid_count = 2 if pool.market == "place" else 3
        winning_horses = order[:paid_count]
        if selection[0] not in winning_horses:
            raise ValueError("_pool_multiplier called on a losing Place/Show wager")
        handle = pool.amounts_cents.get(selection, 0)
        handles_on_winners = [pool.amounts_cents.get((h,), 0) for h in winning_horses]
        if not handle or any(h <= 0 for h in handles_on_winners):
            raise ValueError(f"pools[{pool.id}]: zero winning handle on {winning_horses}")
        remaining = pool.net_cents - sum(handles_on_winners)
        if remaining < 0:
            raise ValueError(
                f"pools[{pool.id}]: negative distributable profit for top "
                f"{paid_count} horses {winning_horses}; minus-pool settlement unsupported")
        ratio = 1 + remaining / (paid_count * handle)
    else:
        if pool.market == "win":
            winning = order[:1]
        elif pool.market == "quinella":
            winning = tuple(sorted(order[:2]))
        else:
            winning = order[:_MARKETS[pool.market]]
        if _key_for_selection(pool.market, selection) != winning:
            raise ValueError("_pool_multiplier called on a losing straight wager")
        handle = pool.amounts_cents.get(winning, 0)
        if handle <= 0:
            raise ValueError(f"pools[{pool.id}]: zero winning handle on {winning}")
        if pool.net_cents < handle:
            raise ValueError(
                f"pools[{pool.id}]: net pool less than winning handle for "
                f"{winning}; minimum-dividend/minus-pool settlement unsupported")
        ratio = pool.net_cents / handle
    return _check_ratio(Fraction(ratio), f"pools[{pool.id}]")


def _offer_wins(offer: _Offer, order: tuple[str, ...],
                place_top: int, show_top: int) -> bool:
    if offer.market == "win":
        return offer.selection[0] == order[0]
    if offer.market == "place":
        return offer.selection[0] in order[:place_top]
    if offer.market == "show":
        return offer.selection[0] in order[:show_top]
    if offer.market == "quinella":
        return set(offer.selection) == set(order[:2])
    return offer.selection == order[:_MARKETS[offer.market]]


def _offer_ratio(offer: _Offer, pools: dict[str, _Pool],
                 order: tuple[str, ...]) -> Fraction:
    """Return the multiplier independently from offers/pool source data."""
    if offer.pool_id is None:
        assert offer.payout_ratio is not None
        return offer.payout_ratio
    return _pool_multiplier(pools[offer.pool_id], offer.selection, order)


def _build_problem(problem: Mapping[str, Any]) -> _Problem:
    problem = _require_mapping(problem, "problem")
    horses_raw = problem.get("horses")
    if (not isinstance(horses_raw, (list, tuple)) or len(horses_raw) < 2 or
            not all(isinstance(h, str) and h.strip() for h in horses_raw)):
        raise ValueError("horses must be a list of at least two nonempty horse IDs")
    horses = tuple(horses_raw)
    if len(set(horses)) != len(horses):
        raise ValueError("horse IDs must be distinct")
    budget = _money_cents(problem.get("budget"), field="budget")
    race_rules = _require_mapping(problem.get("race_rules", {}), "race_rules")
    place_top = race_rules.get("place_pays_top", min(2, len(horses)))
    show_top = race_rules.get("show_pays_top", min(3, len(horses)))
    if (type(place_top) is not int or type(show_top) is not int or
            not (1 <= place_top <= len(horses)) or
            not (place_top <= show_top <= len(horses))):
        raise ValueError("race_rules: require 1 <= place_pays_top <= show_pays_top <= horse count")
    pools = _parse_pools(problem.get("pools", {}), horses,
                         place_top=place_top, show_top=show_top)
    stake_rules = _require_mapping(problem.get("stake_rules", {}), "stake_rules")
    offers_raw = problem.get("offers")
    if not isinstance(offers_raw, list) or not offers_raw:
        raise ValueError("offers must be a nonempty list of priced straight wagers")

    offers: list[_Offer] = []
    seen_ids: set[str] = set()
    for index, raw in enumerate(offers_raw):
        offer = _require_mapping(raw, f"offers[{index}]")
        label = str(offer.get("id", f"offer-{index + 1}"))
        if not label or label in seen_ids:
            raise ValueError(f"offer IDs must be unique and nonempty ({label!r})")
        seen_ids.add(label)
        market = offer.get("market")
        if not isinstance(market, str) or market.lower() not in _MARKETS:
            raise ValueError(f"{label}: unsupported market {market!r}")
        market = market.lower()
        sel_raw = offer.get("selection")
        if (not isinstance(sel_raw, (list, tuple)) or
                len(sel_raw) != _MARKETS[market] or
                not all(isinstance(h, str) for h in sel_raw) or
                len(set(sel_raw)) != len(sel_raw) or
                any(h not in horses for h in sel_raw)):
            raise ValueError(f"{label}: invalid selection for {market}")
        selection = tuple(sel_raw)
        pool_id = offer.get("pool_id")
        if pool_id is not None:
            if not isinstance(pool_id, str) or pool_id not in pools:
                raise ValueError(f"{label}: unknown pool_id {pool_id!r}")
            if pools[pool_id].market != market:
                raise ValueError(
                    f"{label}: pool_id {pool_id!r} is for {pools[pool_id].market}, "
                    f"not {market}")
            if "american_odds" in offer or "decimal_odds" in offer:
                raise ValueError(f"{label}: pool-backed offers must not specify fixed odds")
            ratio, displayed = None, None
        else:
            ratio, displayed = _odds_ratio(offer, label)
        defaults = _require_mapping(stake_rules.get(market, {}), f"stake_rules[{market}]")
        minimum_raw = offer.get("minimum", defaults.get("minimum"))
        increment_raw = offer.get("increment", defaults.get("increment"))
        if minimum_raw is None or increment_raw is None:
            raise ValueError(f"{label}: supply minimum and increment via offer or stake_rules")
        minimum = _money_cents(minimum_raw, field=f"{label}.minimum")
        increment = _money_cents(increment_raw, field=f"{label}.increment")
        increment_mode = offer.get("increment_mode", defaults.get("increment_mode", "from_minimum"))
        if increment_mode not in {"from_minimum", "multiples"}:
            raise ValueError(f"{label}: increment_mode must be from_minimum or multiples")
        max_raw = offer.get("max_stake", defaults.get("max_stake"))
        maximum = (budget if max_raw is None else
                   min(budget, _money_cents(max_raw, field=f"{label}.max_stake", allow_zero=True)))
        book_raw = offer.get("book")
        if book_raw is not None and (not isinstance(book_raw, str) or not book_raw.strip()):
            raise ValueError(f"{label}: book must be a nonempty string when provided")
        offers.append(_Offer(label, book_raw, market, selection, displayed, ratio,
                             pool_id, minimum, increment, increment_mode, maximum))

    book_limits: dict[str, int] = {}
    for name, amount in _require_mapping(problem.get("book_limits", {}), "book_limits").items():
        if not isinstance(name, str) or not name:
            raise ValueError("book_limits keys must be nonempty book names")
        book_limits[name] = _money_cents(amount, field=f"book_limits[{name}]", allow_zero=True)
    if any(name not in {o.book for o in offers} for name in book_limits):
        raise ValueError("book_limits contains a book not referenced by any offer")

    def depth(market: str) -> int:
        return {"win": 1, "place": place_top, "show": show_top,
                "exacta": 2, "quinella": 2, "trifecta": 3,
                "superfecta": 4}[market]

    top = max(depth(o.market) for o in offers)
    if top > len(horses):
        raise ValueError("an offered bet requires more finishing places than horses")
    n_outcomes = 1
    for i in range(top):
        n_outcomes *= len(horses) - i
    if n_outcomes * len(offers) > _MAX_MATRIX_ELEMENTS:
        raise ValueError(
            f"outcome matrix too large ({n_outcomes} outcomes x {len(offers)} bets); "
            "use a smaller market set or a constraint-generation solver")
    # Generate the existing permutations ONCE and reuse them for pool dividends.
    outcomes = tuple(permutations(horses, top))
    wins = np.zeros((len(outcomes), len(offers)), dtype=bool)
    ratios = np.empty((len(outcomes), len(offers)), dtype=object)
    ratios.fill(None)
    for s, order in enumerate(outcomes):
        for i, o in enumerate(offers):
            if _offer_wins(o, order, place_top, show_top):
                wins[s, i] = True
                ratios[s, i] = _offer_ratio(o, pools, order)
    return _Problem(horses, budget, tuple(offers), outcomes, wins, ratios,
                    pools, book_limits, place_top, show_top)


class _MILPModel:
    def __init__(self, p: _Problem, *, minimum_profit_cents: int = 0):
        self.p = p
        self.n = n = len(p.offers)
        self.x = list(range(n))
        self.z = list(range(n, 2*n))
        self.k = list(range(2*n, 3*n))
        self.g = 3*n
        # Share payout variables for equal (offer, payout multiplier) pairs.
        # Fixed odds still use exactly one payout variable per offered bet.
        self.q_by_key: dict[tuple[int, Fraction], int] = {}
        self.scenario_q: list[list[int]] = []
        for row in p.payout_ratios:
            payout_indices: list[int] = []
            for i, ratio in enumerate(row):
                if ratio is None:
                    continue
                key = (i, ratio)
                idx = self.q_by_key.get(key)
                if idx is None:
                    idx = 3*n + 1 + len(self.q_by_key)
                    self.q_by_key[key] = idx
                payout_indices.append(idx)
            self.scenario_q.append(payout_indices)
        self.nvar = 3*n + 1 + len(self.q_by_key)
        self.lb = np.zeros(self.nvar, dtype=float)
        self.ub = np.full(self.nvar, np.inf, dtype=float)
        self.integrality = np.ones(self.nvar, dtype=np.int32)
        self.lb[self.g] = minimum_profit_cents
        self.rows: list[dict[int, float]] = []
        self.row_lb: list[float] = []
        self.row_ub: list[float] = []
        for i, offer in enumerate(p.offers):
            mn, inc, mx = offer.minimum_cents, offer.increment_cents, offer.maximum_cents
            self.ub[self.x[i]] = mx
            self.ub[self.z[i]] = 1
            self.ub[self.k[i]] = mx // inc
            if offer.increment_mode == "from_minimum":
                self.add({self.x[i]: 1, self.z[i]: -mn, self.k[i]: -inc}, 0, 0)
            else:
                self.add({self.x[i]: 1, self.k[i]: -inc}, 0, 0)
                self.add({self.x[i]: 1, self.z[i]: -mn}, 0, np.inf)
            self.add({self.x[i]: 1, self.z[i]: -mx}, -np.inf, 0)

        for (i, ratio), q_index in self.q_by_key.items():
            numer, denom = ratio.numerator, ratio.denominator
            self.ub[q_index] = numer * p.offers[i].maximum_cents // denom
            # q = floor((numer / denom) * stake), in whole cents.
            self.add({q_index: denom, self.x[i]: -numer}, -np.inf, 0)
            self.add({self.x[i]: numer, q_index: -denom}, -np.inf, denom - 1)
        self.add({j: 1 for j in self.x}, -np.inf, p.budget_cents)
        for book, cap in p.book_limits_cents.items():
            self.add({self.x[i]: 1 for i, o in enumerate(p.offers) if o.book == book},
                     -np.inf, cap)
        for payout_indices in self.scenario_q:
            row = {j: -1 for j in self.x}
            for q_index in payout_indices:
                row[q_index] = row.get(q_index, 0) + 1
            row[self.g] = -1
            self.add(row, 0, np.inf)

    def add(self, coeffs: dict[int, float], lower: float, upper: float) -> None:
        self.rows.append(coeffs)
        self.row_lb.append(lower)
        self.row_ub.append(upper)

    def solve(self, objective: str, *, fixed_count: int | None = None,
              time_limit: float | None = None):
        c = np.zeros(self.nvar)
        if objective == "max_profit":
            c[self.g] = -1
        elif objective == "min_bets":
            c[self.z] = 1
        else:
            raise ValueError(f"Unknown objective: {objective}")
        rows = list(self.rows)
        lowers = list(self.row_lb)
        uppers = list(self.row_ub)
        if fixed_count is not None:
            rows.append({j: 1 for j in self.z})
            lowers.append(fixed_count)
            uppers.append(fixed_count)
        r_ids: list[int] = []
        c_ids: list[int] = []
        values: list[float] = []
        for r, row in enumerate(rows):
            for j, value in row.items():
                if value:
                    r_ids.append(r)
                    c_ids.append(j)
                    values.append(value)
        matrix = coo_array((np.asarray(values, dtype=float),
                            (np.asarray(r_ids, dtype=np.int32),
                             np.asarray(c_ids, dtype=np.int32))),
                           shape=(len(rows), self.nvar)).tocsc()
        options: dict[str, Any] = {"mip_rel_gap": 0.0, "presolve": True}
        if time_limit is not None:
            if not isfinite(time_limit) or time_limit <= 0:
                raise ValueError("time_limit must be a positive number of seconds")
            options["time_limit"] = float(time_limit)
        return milp(c, integrality=self.integrality,
                    bounds=Bounds(self.lb, self.ub),
                    constraints=LinearConstraint(matrix, lowers, uppers),
                    options=options)


def _as_int(vector: np.ndarray, idx: int) -> int:
    value = float(vector[idx])
    rounded = round(value)
    if abs(value - rounded) > 1e-4:
        raise RuntimeError("MILP returned a nonintegral variable; solution not certified")
    return int(rounded)


def _checked_output(p: _Problem, model: _MILPModel, result: Any, *,
                    objective: str, threshold_cents: int = 0) -> dict[str, Any]:
    if result.status == 2:
        return {
            "status": "infeasible",
            "objective": objective,
            "message": "No allocation meets all constraints at the specified profit threshold.",
            "minimum_profit_required": _money(threshold_cents),
            "scenarios_checked": len(p.outcomes),
        }
    if result.status != 0 or result.x is None:
        raise RuntimeError(
            f"MILP did not prove optimality (status={result.status}): {result.message}")

    vector = result.x
    stakes = [_as_int(vector, i) for i in model.x]
    z_values = [_as_int(vector, i) for i in model.z]
    guaranteed = _as_int(vector, model.g)
    for i, o in enumerate(p.offers):
        st, zi = stakes[i], z_values[i]
        if zi not in {0, 1} or (st > 0) != (zi == 1):
            raise RuntimeError("MILP wager activation is inconsistent")
        if st:
            if not o.minimum_cents <= st <= o.maximum_cents:
                raise RuntimeError("MILP wager violates a min/max constraint")
            valid = ((st - o.minimum_cents) % o.increment_cents == 0 if
                     o.increment_mode == "from_minimum" else st % o.increment_cents == 0)
            if not valid:
                raise RuntimeError("MILP wager violates an increment constraint")
    total = sum(stakes)
    if total > p.budget_cents:
        raise RuntimeError("MILP allocation exceeds budget")
    for book, cap in p.book_limits_cents.items():
        if sum(st for st, o in zip(stakes, p.offers) if o.book == book) > cap:
            raise RuntimeError("MILP allocation exceeds a book limit")

    # Independent verification: for EVERY outcome, recalculate the dividend
    # from the source pool and the selected stake with exact integer arithmetic.
    # Never rely on the MILP's q values when computing the returned guarantee.
    net: list[int] = []
    payout_by_offer: list[list[int]] = [[] for _ in p.offers]
    for s, order in enumerate(p.outcomes):
        paid = 0
        for i, o in enumerate(p.offers):
            if not stakes[i] or not _offer_wins(o, order, p.place_pays_top, p.show_pays_top):
                continue
            ratio = _offer_ratio(o, p.pools, order)
            if ratio != p.payout_ratios[s, i] or not p.wins[s, i]:
                raise RuntimeError("Model scenario ratio disagrees with pool settlement rules")
            amount = ratio.numerator * stakes[i] // ratio.denominator
            if _as_int(vector, model.q_by_key[(i, ratio)]) != amount:
                raise RuntimeError("MILP payout rounding is inconsistent")
            payout_by_offer[i].append(amount)
            paid += amount
        net.append(paid - total)
    worst_net = min(net)
    if worst_net < guaranteed or worst_net < threshold_cents:
        raise RuntimeError("MILP's predicted minimum profit failed exact outcome verification")
    worst_orders = [list(p.outcomes[i]) for i, value in enumerate(net)
                    if value == worst_net][:8]
    chosen = []
    for i, o in enumerate(p.offers):
        if not stakes[i]:
            continue
        item: dict[str, Any] = {
            "id": o.id, "book": o.book, "market": o.market,
            "selection": list(o.selection),
        }
        if o.pool_id is None:
            # Preserve the original fixed-odds output fields and ordering.
            item["odds"] = o.displayed_odds
            item["stake"] = _money(stakes[i])
            assert o.payout_ratio is not None
            item["payout_if_wins"] = _money(
                o.payout_ratio.numerator * stakes[i] // o.payout_ratio.denominator)
        else:
            item["stake"] = _money(stakes[i])
            item["pool_id"] = o.pool_id
            item["minimum_payout_if_wins"] = _money(min(payout_by_offer[i]))
            item["maximum_payout_if_wins"] = _money(max(payout_by_offer[i]))
        chosen.append(item)
    return {
        "status": "optimal_arbitrage" if worst_net > 0 else "no_arbitrage",
        "objective": objective,
        "budget": _money(p.budget_cents),
        "total_staked": _money(total),
        "minimum_payout": _money(total + worst_net),
        "guaranteed_profit": _money(worst_net),
        "number_of_bets": len(chosen),
        "selected_bets": chosen,
        "worst_case_finishes": worst_orders,
        "scenarios_checked": len(p.outcomes),
        "all_scenarios_verified": True,
        "optimality_proven": True,
    }


def maximize_guaranteed_profit(
    problem: Mapping[str, Any], *, time_limit: float | None = None
) -> dict[str, Any]:
    """Maximize minimum net profit under fixed odds and/or fixed pool snapshots.

    Zero wagers are permitted if no positive modeled arbitrage is available.
    Spending the entire budget is optional.
    """
    parsed = _build_problem(problem)
    model = _MILPModel(parsed)
    return _checked_output(parsed, model, model.solve("max_profit", time_limit=time_limit),
                           objective="max_profit")


def minimize_bets_with_arbitrage(
    problem: Mapping[str, Any], *, minimum_profit: str = "0.01",
    tie_break: str = "max_profit", time_limit: float | None = None
) -> dict[str, Any]:
    """Minimize nonzero straight wagers with guaranteed modeled net profit.

    With tie_break='max_profit', a second MILP maximizes profit *among the
    minimum-count portfolios*. Use 'none' to skip the second optimization.
    """
    parsed = _build_problem(problem)
    required = _money_cents(minimum_profit, field="minimum_profit")
    if tie_break not in {"max_profit", "none"}:
        raise ValueError("tie_break must be 'max_profit' or 'none'")
    model = _MILPModel(parsed, minimum_profit_cents=required)
    first = model.solve("min_bets", time_limit=time_limit)
    if first.status == 2:
        return _checked_output(parsed, model, first,
                               objective="min_bets", threshold_cents=required)
    if first.status != 0 or first.x is None:
        raise RuntimeError(f"MILP did not prove the minimum bet count: {first.message}")
    count = sum(_as_int(first.x, j) for j in model.z)
    final = (model.solve("max_profit", fixed_count=count, time_limit=time_limit)
             if tie_break == "max_profit" else first)
    output = _checked_output(parsed, model, final,
                             objective="min_bets", threshold_cents=required)
    if output["status"] == "optimal_arbitrage" and output["number_of_bets"] != count:
        raise RuntimeError("Tie-breaking changed the optimal number of wagers")
    output["minimum_profit_required"] = _money(required)
    output["tie_break"] = tie_break
    return output
