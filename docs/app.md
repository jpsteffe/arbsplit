# Race Arbitrage Studio — FastAPI + static UI

The web interface for the **unchanged** `src/arbitrage_optimizer.py`. The optimizer reference is in [optimizer.md](optimizer.md). The site is served by FastAPI, uses plain HTML/CSS/JavaScript with no frontend build step, and sends calculations to **one API endpoint**, `POST /api/calculate`.

**Prairie Meadows (Altoona, Iowa) is selected by default.** The racetrack dropdown also includes Oaklawn Park, Keeneland, and Custom track. Track presets supply *editable assumptions*, not an official or live quote.

## Quick start

Requires Python 3.10 or newer.

```bash
python -m pip install -r src/requirements.txt
cd src
uvicorn app:app --reload --host 127.0.0.1 --port 8000
```

Open <http://127.0.0.1:8000/>. Use **Load hypothetical example** to see the complete workflow with fabricated runners, two fabricated external fixed Win prices, and a fabricated Place pool. The example is *not* a real Prairie Meadows race.

Run all tests from the repository root:

```bash
python -m pip install -r tests/requirements.txt
sh tests/run.sh
```

The `test` workflow runs the same script on every pull request.

## Using the form

1. Select **Prairie Meadows**, specify the race number and available budget.
2. Enter every runner (program number plus optional name). There must be two or more runners.
3. For pari-mutuel bets, add a **Win, Place or Show pool**. Enter the current stake amount wagered on *each* runner in that pool; the form sums the amounts into `gross_pool`. The takeout percentage starts at a track estimate but is editable. The backend needs a **complete, strictly positive** handle distribution for all runners, not just the one you intend to back.
4. Add priced wagers. Fixed-odds wagers require one external **American** price (e.g. `+400`, `-110`) or a **decimal** price (e.g. `5.00`). Pool-backed wagers reference one of the pools. Use “Create ... offers for every runner” after entering a pool, if useful.
5. Review **Wager sizes & limits**, especially actual minimums and allowed increments at the current venue/channel. Optionally add a per-wager maximum stake.
6. Compare **maximum worst-case profit** versus **fewest bets meeting a positive minimum-profit threshold**, or run either one alone.

The **Advanced JSON** panel accepts any original optimizer problem, including exotic markets, complete exotic pool snapshots, book limits and per-wager overrides. Check **Calculate using edited JSON** when you want that input to override the form. Existing example programs and optimizer tests are included unchanged.

## One calculation endpoint

`POST /api/calculate`

```json
{
  "problem": {
    "horses": ["1", "2"],
    "budget": "200.00",
    "stake_rules": {"win": {"minimum": "2.00", "increment": "2.00"}},
    "offers": [
      {"id": "a", "market": "win", "selection": ["1"], "american_odds": 110},
      {"id": "b", "market": "win", "selection": ["2"], "american_odds": 110}
    ]
  },
  "mode": "both",
  "minimum_profit": "0.01",
  "tie_break": "max_profit",
  "time_limit": 12
}
```

- `mode`: `"both"` (default), `"max_profit"`, or `"min_bets"`.
- `minimum_profit`: positive decimal **string**; used only for `min_bets`.
- `tie_break`: `"max_profit"` (default) or `"none"`.
- `time_limit`: positive seconds, at most 60, **per solver call**. A two-phase minimum-bet optimization may use two calls.

The response is `{ "results": { "max_profit": { ... }, "min_bets": { ... } } }` with the **original** result dictionaries unchanged. A `422` response indicates invalid input; `503` indicates a solver run that could not certify an optimum. The server runs CPU-heavy work in a threadpool so it doesn't block serving static files.

### Source files

```
src/app.py                        FastAPI single endpoint / static hosting
src/static/index.html             Static UI
src/static/styles.css             UI styling
src/static/app.js                 UI state, form->JSON conversion and results
src/static/tracks.js              Track presets / linked sources
src/arbitrage_optimizer.py        Optimizer (unchanged)
src/requirements.txt              Runtime dependencies
tests/test_arbitrage_optimizer.py Optimizer tests (unchanged)
tests/test_app.py                 API / static-file smoke tests
tests/requirements.txt            Test dependencies (adds httpx)
examples/example_arbitrage_usage.py  Optimizer examples (unchanged)
```

## Prairie Meadows preset: sources and caveats

Track selection does **not** change the optimization algorithm; it fills initial stake rules and estimated pool takeout percentages. Verify all values against current race-program and tote information.

| Market | Starter minimum / step | Estimated takeout |
|---|---:|---:|
| Win / Place / Show | $2.00 | 17% |
| Exacta | $2.00 | 20% |
| Quinella | $2.00 | 20% |
| Trifecta | $0.50 | 20% |
| Superfecta | $0.10 | 20% |

- **W/P/S $2**: [Iowa general wagering rules](https://rules.iowa.gov/Notice/Details/0186D) and [Prairie Meadows' betting guide](https://www.prairiemeadows.com/community/articles/blog/wagering-101).
- **2026 chart payout denominations**: [Equibase Prairie Meadows results, September 25, 2026](https://tvg.equibase.com/static/chart/summary/PRM092526USA3-EQB.html) show $2 exacta and quinella, $0.50 trifecta and $0.10 superfecta. A denomination *shown on the chart* does not independently establish the **lowest accepted wager** or step. Prairie Meadows' [own guide](https://www.prairiemeadows.com/community/articles/blog/wagering-101) also explicitly mentions $0.10 superfectas. The exacta/quinella $2 minimum and all exotic increments should be **checked at the betting window**.
- **Takeout**: [In the Money's track-by-track takeout comparison, updated November 23, 2026](https://inthemoneypodcast.com/horse-racing-takeout-rates/) lists PRM 17% WPS and 20% Exacta, Trifecta and Superfecta. Quinella 20% is a tentative similarly categorized assumption, **not independently confirmed by this table**. Older third-party sources disagree on trifecta takeout, so these inputs remain editable, and no rate is represented as an official track guarantee.
- Iowa's [approved pari-mutuel wager procedures](https://irgc.iowa.gov/media/130/download?inline=) describe win, place and show pool arithmetic, including **breakage**. The supplied optimizer intentionally omits actual breakage, minimum dividend rules and exceptional settlement scenarios.

Oaklawn and Keeneland takeout presets are sourced from the same November 2026 comparison table; their *minimum wager* values are **unverified placeholders**. Quinella takeout is left blank for those tracks.

## Important limitations

This is a **research calculator, not an execution or live-trading product**. Input prices and snapshots are provided by the user; there is **no** scraper, sportsbook connection, live race card, live odds, pool-feed access, bet placement, or application-level authentication. Real pari-mutuel pool payouts change when money enters the pool, so an optimizer result labeled `guaranteed_profit` only means the lowest result **under the input assumptions**, not a guarantee of actual profitability.

The original solver models one race, distinct finishers, straight selections, and exact per-cent flooring in a fixed snapshot. It does not model late handle, effects of your own wagers, breakage, actual tote rounding, minus-pool/minimum payoffs, coupled entries, scratches, refunds, dead heats, or other race exceptions. When run locally, bind the server to `127.0.0.1`. The deployed service is not rate-limited. Identity-Aware Proxy is the only access control, so see [deployment.md](deployment.md) for who can call it.
