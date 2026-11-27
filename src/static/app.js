(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const MARKETS = ["win", "place", "show", "exacta", "quinella", "trifecta", "superfecta"];
  const POOL_MARKETS = ["win", "place", "show"];
  const DEPTH = { win: 1, place: 1, show: 1, exacta: 2, quinella: 2, trifecta: 3, superfecta: 4 };
  const TRACKS = window.TRACK_PRESETS;
  let sequence = 0;
  let state;
  let hasResults = false;

  const uid = (prefix) => `${prefix}-${++sequence}`;
  const html = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  const marketName = (market) => market.charAt(0).toUpperCase() + market.slice(1);
  const track = () => TRACKS.find((t) => t.id === state.trackId) || TRACKS[0];
  const option = (value, label, chosen) => `<option value="${html(value)}" ${value === chosen ? "selected" : ""}>${html(label)}</option>`;
  const cardDelete = (title, attr, id) => `<button type="button" class="icon-button" title="${html(title)}" aria-label="${html(title)}" data-action="${html(attr)}" data-id="${html(id)}">×</button>`;

  function cents(value, label, allowZero = false) {
    const v = String(value ?? "").trim();
    if (!/^(0|[1-9]\d*)(\.\d{1,2})?$/.test(v)) throw new Error(`${label}: enter a dollar amount, such as 2.00 (no commas).`);
    const [whole, dec = ""] = v.split(".");
    const n = Number(whole) * 100 + Number(dec.padEnd(2, "0"));
    if (!Number.isSafeInteger(n) || n < 0 || (!allowZero && n === 0)) throw new Error(`${label}: enter a ${allowZero ? "nonnegative" : "positive"} amount.`);
    return n;
  }
  function money(value, label, allowZero = false) {
    const n = cents(value, label, allowZero);
    return `${Math.floor(n / 100)}.${String(n % 100).padStart(2, "0")}`;
  }
  function showMoney(n) { return `$${Math.floor(n / 100).toLocaleString("en-US")}.${String(n % 100).padStart(2, "0")}`; }
  function percentRate(v, label) {
    const str = String(v ?? "").trim();
    if (!/^(0|[1-9]\d?)(\.\d{1,2})?$/.test(str)) throw new Error(`${label}: enter a percentage from 0 to less than 100, e.g. 17 or 19.5.`);
    const [whole, dec = ""] = str.split(".");
    const basis = Number(whole) * 100 + Number(dec.padEnd(2, "0"));
    if (basis >= 10000) throw new Error(`${label}: takeout must be less than 100%.`);
    return `0.${String(basis).padStart(4, "0")}`.replace(/0+$/, "").replace(/\.$/, "");
  }
  function rulesFor(t) {
    return Object.fromEntries(MARKETS.map((m) => [m, {
      minimum: t.minimums[m] || "1.00",
      increment: t.minimums[m] || "1.00",
      increment_mode: "multiples"
    }]));
  }
  function newHorse(number, name = "") { return { uid: uid("horse"), number: String(number), name }; }
  function initialState() {
    return {
      trackId: "PRM", raceNumber: "1", budget: "100.00",
      horses: Array.from({ length: 6 }, (_, i) => newHorse(i + 1)),
      rules: rulesFor(TRACKS[0]), pools: [], offers: []
    };
  }
  function horseLabel(h) { return `#${h.number || "?"}${h.name.trim() ? ` ${h.name.trim()}` : ""}`; }
  function newOffer(market = "win", source = "fixed") {
    const n = state.offers.length + 1;
    const pool = state.pools.find((p) => p.market === market);
    return {
      uid: uid("offer"), id: `wager-${n}`, market,
      selection: state.horses.slice(0, DEPTH[market]).map((h) => h.uid),
      source: source === "pool" && pool ? "pool" : "fixed",
      poolUid: pool?.uid || "", oddsType: "american", odds: "", book: "", maxStake: ""
    };
  }
  function newPool(market = "win") {
    return {
      uid: uid("pool"), id: `${market}-pool-${sequence}`, market,
      takeout: track().takeout[market] || "", amounts: {}
    };
  }
  function markDirty() {
    if (hasResults) {
      $("result-status").textContent = "STALE INPUTS";
      $("result-status").className = "status-indicator loading";
    }
  }
  function resetResults() {
    hasResults = false;
    $("result-status").textContent = "READY";
    $("result-status").className = "status-indicator";
    $("error-area").hidden = true;
    $("results-content").innerHTML = `<div class="placeholder"><div class="placeholder-graphic" aria-hidden="true"><span>↗</span><span>↘</span><span>→</span></div><h3>The board is clear.</h3><p>Add runners and wagers, then calculate to see results across every modeled finish.</p><p class="placeholder-hint">Or load the hypothetical example to try it immediately.</p></div>`;
  }
  function setStatus(text, type = "") {
    $("result-status").textContent = text;
    $("result-status").className = `status-indicator ${type}`;
  }

  function renderTrack() {
    $("track-select").innerHTML = TRACKS.map((t) => option(t.id, `${t.name} — ${t.location}`, state.trackId)).join("");
    $("race-number").value = state.raceNumber;
    $("budget").value = state.budget;
    const t = track();
    $("preset-info").innerHTML = `<div class="preset-top"><span class="preset-name">${html(t.short)}</span><span class="preset-source">Editable starting values · not live data</span></div><p>${html(t.note)}</p><div class="source-links">${t.sources.map((s) => `<a href="${html(s.url)}" target="_blank" rel="noopener noreferrer">${html(s.label)} ↗</a>`).join("")}</div>`;
  }
  function renderRunners() {
    $("runner-count").textContent = `${state.horses.length} RUNNERS`;
    $("runners-list").innerHTML = state.horses.map((h) => `<div class="runner-row" data-horse="${html(h.uid)}">
      <input aria-label="Program number" class="number" data-field="number" type="text" maxlength="12" value="${html(h.number)}" placeholder="1" autocomplete="off">
      <input aria-label="Horse name for number ${html(h.number)}" data-field="name" type="text" maxlength="90" value="${html(h.name)}" placeholder="Horse name" autocomplete="off">
      ${cardDelete("Remove runner", "remove-horse", h.uid)}
    </div>`).join("");
  }
  function handleTotal(pool) {
    let total = 0;
    for (const h of state.horses) {
      const v = String(pool.amounts[h.uid] ?? "").trim();
      if (v && /^(0|[1-9]\d*)(\.\d{1,2})?$/.test(v)) total += cents(v, "Pool amount", true);
    }
    return total;
  }
  function renderPools() {
    const el = $("pools-list");
    if (!state.pools.length) {
      el.innerHTML = `<div class="empty-note"><span>◎</span>No pools yet. Add a pool to enter the amounts wagered on each runner.</div>`;
      return;
    }
    el.innerHTML = state.pools.map((p, i) => `<div class="pool-card" data-pool="${html(p.uid)}">
      <div class="pool-card-head"><div><span class="card-index">POOL ${String(i + 1).padStart(2, "0")}</span> <span class="card-subtle">/ ${html(p.id)}</span></div>${cardDelete("Remove pool", "remove-pool", p.uid)}</div>
      <div class="pool-card-main">
        <div class="pool-settings">
          <label class="field"><span>Pool market</span><select data-field="market">${POOL_MARKETS.map((m) => option(m, marketName(m), p.market)).join("")}</select></label>
          <label class="field"><span>Takeout <small>% editable</small></span><input data-field="takeout" inputmode="decimal" type="text" placeholder="e.g. 17" value="${html(p.takeout)}"></label>
        </div>
        <div class="pool-handle-header"><span>Amount on each runner <small>(USD)</small></span><span data-role="total">Total ${showMoney(handleTotal(p))}</span></div>
        <div class="handle-grid">${state.horses.map((h) => `<label class="handle-row"><span title="${html(horseLabel(h))}">${html(horseLabel(h))}</span><input aria-label="${html(p.market)} pool amount for ${html(horseLabel(h))}" type="text" inputmode="decimal" data-amount-horse="${html(h.uid)}" value="${html(p.amounts[h.uid] ?? "")}" placeholder="0.00" autocomplete="off"></label>`).join("")}</div>
        <p class="offer-footnote">Every runner needs a positive amount for this complete-snapshot model. The total is calculated automatically.</p>
        <button type="button" class="add-link" data-action="add-pool-offers" data-id="${html(p.uid)}">+ Create ${html(p.market)} offers for every runner</button>
      </div>
    </div>`).join("");
  }
  function selectionControls(offer) {
    return Array.from({ length: DEPTH[offer.market] }, (_, i) => `<label><span class="offer-select-label">${DEPTH[offer.market] > 1 ? `Finish ${i + 1}` : "Runner"}</span><select data-selection-index="${i}" aria-label="Selection ${i + 1}">${state.horses.map((h) => option(h.uid, horseLabel(h), offer.selection[i] || "")).join("")}</select></label>`).join("");
  }
  function renderOffers() {
    $("offer-count").textContent = `${state.offers.length} OFFERS`;
    const el = $("offers-list");
    if (!state.offers.length) {
      el.innerHTML = `<div class="empty-note"><span>＋</span>No wagers entered. Add individual prices or create all Win wagers at once.</div>`;
      return;
    }
    el.innerHTML = state.offers.map((o, i) => {
      const available = state.pools.filter((p) => p.market === o.market);
      return `<div class="offer-card" data-offer="${html(o.uid)}">
        <div class="offer-card-head"><span class="card-index">WAGER ${String(i + 1).padStart(2, "0")}</span>${cardDelete("Remove wager", "remove-offer", o.uid)}</div>
        <div class="offer-card-main"><div class="offer-fields">
          <label class="field"><span>Wager type</span><select data-field="market">${MARKETS.map((m) => option(m, marketName(m), o.market)).join("")}</select></label>
          <label class="field"><span>Price source</span><select data-field="source">${option("fixed", "Fixed odds / external", o.source)}${option("pool", "Pari-mutuel pool", o.source)}</select></label>
          <div class="full"><div class="offer-selection">${selectionControls(o)}</div></div>
          ${o.source === "fixed" ? `<div class="field full"><span>Price</span><div class="offer-odds"><select aria-label="Odds format" data-field="oddsType">${option("american", "American", o.oddsType)}${option("decimal", "Decimal", o.oddsType)}</select><input data-field="odds" aria-label="Fixed odds" type="text" inputmode="decimal" value="${html(o.odds)}" placeholder="${o.oddsType === "american" ? "e.g. +400 or -110" : "e.g. 5.00"}"></div></div>` : `<label class="field full"><span>Pool</span><select data-field="poolUid"><option value="">Choose matching pool</option>${available.map((p) => option(p.uid, `${p.id} (${marketName(p.market)})`, o.poolUid)).join("")}</select>${!available.length ? `<span class="offer-footnote">Add a ${html(o.market)} pool above before using a pool price.</span>` : ""}</label>`}
          <label class="field"><span>Book / source <small>optional</small></span><input data-field="book" type="text" maxlength="80" placeholder="e.g. Book A" value="${html(o.book)}"></label>
          <label class="field"><span>Max stake <small>USD · optional</small></span><input data-field="maxStake" type="text" inputmode="decimal" placeholder="No limit" value="${html(o.maxStake)}"></label>
        </div></div></div>`;
    }).join("");
  }
  function renderRules() {
    $("stake-rules-list").innerHTML = `<div class="rule-grid-head"><span>MARKET</span><span>MIN $</span><span>STEP $</span><span>INCREMENT MODE</span></div>` + MARKETS.map((market) => {
      const r = state.rules[market];
      return `<div class="rule-row" data-market="${html(market)}"><span class="rule-label">${html(marketName(market))}</span><input type="text" data-field="minimum" inputmode="decimal" value="${html(r.minimum)}" aria-label="${market} minimum stake"><input type="text" data-field="increment" inputmode="decimal" value="${html(r.increment)}" aria-label="${market} stake increment"><select data-field="increment_mode" aria-label="${market} increment mode">${option("multiples", "Multiples", r.increment_mode)}${option("from_minimum", "From min", r.increment_mode)}</select></div>`;
    }).join("");
  }
  function renderAll() { renderTrack(); renderRunners(); renderPools(); renderOffers(); renderRules(); }

  function buildProblem() {
    if (state.horses.length < 2) throw new Error("Add at least two runners.");
    const horses = state.horses.map((h) => h.number.trim());
    if (horses.some((v) => !v)) throw new Error("Every runner needs a program number.");
    if (new Set(horses).size !== horses.length) throw new Error("Runner program numbers must be unique; use distinct IDs for coupled entries.");
    if (!state.offers.length) throw new Error("Add at least one available wager before calculating.");
    const numberByUid = Object.fromEntries(state.horses.map((h) => [h.uid, h.number.trim()]));
    const rules = {};
    for (const m of MARKETS) {
      const r = state.rules[m];
      rules[m] = { minimum: money(r.minimum, `${marketName(m)} minimum`), increment: money(r.increment, `${marketName(m)} increment`), increment_mode: r.increment_mode };
    }
    const referenced = new Set();
    const offers = state.offers.map((o, i) => {
      const selections = o.selection.slice(0, DEPTH[o.market]);
      if (selections.length !== DEPTH[o.market] || selections.some((uid) => !numberByUid[uid])) throw new Error(`Wager ${i + 1}: select ${DEPTH[o.market]} valid runner(s).`);
      if (new Set(selections).size !== selections.length) throw new Error(`Wager ${i + 1}: choose different runners for each finishing position.`);
      if (DEPTH[o.market] > horses.length) throw new Error(`Wager ${i + 1}: ${marketName(o.market)} requires at least ${DEPTH[o.market]} runners.`);
      const entry = { id: o.id, market: o.market, selection: selections.map((uid) => numberByUid[uid]) };
      if (o.source === "pool") {
        const p = state.pools.find((p) => p.uid === o.poolUid);
        if (!p || p.market !== o.market) throw new Error(`Wager ${i + 1}: choose an existing ${o.market} pool.`);
        entry.pool_id = p.id;
        referenced.add(p.uid);
      } else if (o.oddsType === "american") {
        const text = String(o.odds).trim();
        if (!/^[+-]?\d+$/.test(text) || Number(text) === 0 || !Number.isSafeInteger(Number(text))) throw new Error(`Wager ${i + 1}: enter valid nonzero American odds, e.g. +400 or -110.`);
        entry.american_odds = Number(text);
      } else {
        const text = String(o.odds).trim();
        if (!/^\d+(\.\d+)?$/.test(text) || !(Number(text) > 1)) throw new Error(`Wager ${i + 1}: decimal odds must be greater than 1.00.`);
        entry.decimal_odds = text;
      }
      if (o.book.trim()) entry.book = o.book.trim();
      if (o.maxStake.trim()) entry.max_stake = money(o.maxStake, `Wager ${i + 1} maximum`, true);
      return entry;
    });
    const pools = {};
    for (const p of state.pools.filter((p) => referenced.has(p.uid))) {
      const amounts = {};
      let total = 0;
      for (const h of state.horses) {
        const amount = money(p.amounts[h.uid], `${p.id} handle on #${h.number}`);
        amounts[numberByUid[h.uid]] = amount;
        total += cents(amount, "pool handle");
      }
      pools[p.id] = { market: p.market, gross_pool: money(`${Math.floor(total / 100)}.${String(total % 100).padStart(2, "0")}`, "total pool"), takeout_rate: percentRate(p.takeout, `${p.id} takeout`), amounts };
    }
    if (new Set(state.offers.map((o) => o.id)).size !== state.offers.length) throw new Error("Wager IDs must be unique.");
    return {
      horses, budget: money(state.budget, "Budget"),
      race_rules: { place_pays_top: Math.min(2, horses.length), show_pays_top: Math.min(3, horses.length) },
      stake_rules: rules, ...(Object.keys(pools).length ? { pools } : {}), offers
    };
  }

  function renderResultSection(mode, result, nameMap) {
    const title = mode === "max_profit" ? "Maximum worst-case profit" : "Fewest qualifying wagers";
    if (result.status === "infeasible") return `<div class="result-card"><div class="result-card-heading"><h3>${title}</h3><span class="result-badge off">INFEASIBLE</span></div><div class="infeasible">No portfolio can reach the requested modeled minimum of <strong>$${html(result.minimum_profit_required)}</strong> with these available offers and limits. Try a smaller threshold or different offers.</div><div class="result-note">${html(result.scenarios_checked)} finish scenarios were evaluated.</div></div>`;
    const positive = result.status === "optimal_arbitrage";
    const bets = result.selected_bets || [];
    const displaySel = (s) => s.map((x) => { const n = nameMap[x]; return `#${x}${n ? ` ${n}` : ""}`; }).join(" · ");
    return `<div class="result-card">
      <div class="result-card-heading"><h3>${title}</h3><span class="result-badge ${positive ? "" : "off"}">${positive ? "MODELED ARBITRAGE" : "NO ARBITRAGE"}</span></div>
      <div class="metric-primary"><div class="metric-label">${mode === "max_profit" ? "MAX WORST-CASE NET" : "WORST-CASE NET AT MIN COUNT"}</div><div class="metric-value">$${html(result.guaranteed_profit)}</div><div class="metric-help">${positive ? "Positive under every modeled finish at supplied prices" : "No positive profit proven under supplied prices"}</div></div>
      <div class="metric-grid"><div class="metric-box"><div class="val">$${html(result.total_staked)}</div><div class="lab">Total stake</div></div><div class="metric-box"><div class="val">${html(result.number_of_bets)}</div><div class="lab">Wagers</div></div><div class="metric-box"><div class="val">${html(result.scenarios_checked)}</div><div class="lab">Finishes tested</div></div></div>
      ${bets.length ? `<div class="result-subtitle">Stake allocation</div><table class="bet-table"><thead><tr><th>WAGER</th><th>PRICE / PAYOUT</th><th>STAKE</th></tr></thead><tbody>${bets.map((b) => `<tr><td><div class="bet-selection">${html(displaySel(b.selection))}</div><div class="bet-market">${html(b.market)}${b.book ? ` · ${html(b.book)}` : ""}</div></td><td>${b.pool_id ? `<div class="bet-payout">Pool · ${html(b.pool_id)}<div>${html(b.minimum_payout_if_wins)}–${html(b.maximum_payout_if_wins)} payout</div></div>` : `<div>${html(b.odds)}</div><div class="bet-payout">${html(b.payout_if_wins)} if wins</div>`}</td><td><strong>$${html(b.stake)}</strong></td></tr>`).join("")}</tbody></table>` : `<div class="result-note">No stakes selected; under these inputs there is no positive modeled arbitrage.</div>`}
      ${result.worst_case_finishes?.length ? `<div class="result-subtitle">Worst-case finish orders</div><div class="scenario-chips">${result.worst_case_finishes.map((order) => `<span class="scenario-chip">${html(order.map((n) => `#${n}`).join(" › "))}</span>`).join("")}</div>` : ""}
      <div class="result-note">${html(result.scenarios_checked)} modeled scenarios independently verified · ${result.optimality_proven ? "Optimality proven by solver" : "Not certified"}. ${mode === "min_bets" ? `Threshold $${html(result.minimum_profit_required)}; tie-break ${html(result.tie_break)}.` : ""}</div>
    </div>`;
  }
  function renderResults(results, problem) {
    const nameMap = Object.fromEntries(state.horses.map((h) => [h.number.trim(), h.name.trim()]));
    const modes = ["max_profit", "min_bets"].filter((m) => Object.prototype.hasOwnProperty.call(results, m));
    $("results-content").innerHTML = modes.map((m) => renderResultSection(m, results[m], nameMap)).join("");
    setStatus("CALCULATED", "done");
    $("error-area").hidden = true;
    hasResults = true;
  }
  function showError(message) {
    $("error-area").textContent = String(message);
    $("error-area").hidden = false;
    setStatus("ERROR", "error");
  }
  async function calculate(event) {
    event?.preventDefault();
    const button = $("run-btn");
    if (button.disabled) return;
    let problem;
    try {
      problem = $("use-json").checked ? JSON.parse($("json-editor").value) : buildProblem();
    } catch (e) {
      showError(e instanceof SyntaxError ? `Invalid JSON: ${e.message}` : e.message);
      return;
    }
    const payload = {
      problem, mode: $("mode").value,
      minimum_profit: $("minimum-profit").value.trim(),
      tie_break: $("tie-break").value,
      time_limit: Number($("time-limit").value)
    };
    try {
      payload.minimum_profit = money(payload.minimum_profit, "Minimum modeled profit");
      if (!Number.isFinite(payload.time_limit) || payload.time_limit <= 0 || payload.time_limit > 60) throw new Error("Solver timeout must be between 1 and 60 seconds.");
      button.disabled = true;
      $("run-button-label").textContent = "Optimizing…";
      setStatus("SOLVING", "loading");
      $("error-area").hidden = true;
      const response = await fetch("/api/calculate", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload)
      });
      const data = await response.json();
      if (!response.ok) {
        const detail = data.detail;
        throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
      }
      renderResults(data.results, problem);
    } catch (e) {
      showError(e.message || "Calculation failed. Please check your inputs.");
    } finally {
      button.disabled = false;
      $("run-button-label").textContent = "Calculate portfolios";
    }
  }

  function demo() {
    state = initialState();
    state.budget = "100.00";
    state.raceNumber = "DEMO";
    state.horses = [newHorse("1", "Sample A"), newHorse("2", "Sample B"), newHorse("3", "Sample C")];
    const p = newPool("place");
    p.id = "demo-place-pool";
    p.takeout = "17";
    p.amounts = {
      [state.horses[0].uid]: "40.00",
      [state.horses[1].uid]: "40.00",
      [state.horses[2].uid]: "20.00"
    };
    state.pools.push(p);
    const a = newOffer("win"); a.id = "sample-a-win"; a.selection = [state.horses[0].uid]; a.odds = "+900"; a.book = "Hypothetical fixed";
    const b = newOffer("win"); b.id = "sample-b-win"; b.selection = [state.horses[1].uid]; b.odds = "+900"; b.book = "Hypothetical fixed";
    const c = newOffer("place", "pool"); c.id = "sample-c-place"; c.selection = [state.horses[2].uid]; c.poolUid = p.uid; c.book = "Hypothetical pool";
    state.offers.push(a, b, c);
    $("use-json").checked = false;
    renderAll(); resetResults();
    $("preset-info").insertAdjacentHTML("beforeend", '<p><strong>DEMO LOADED:</strong> The runners, odds and $100 pool are invented for testing. They are not an actual Prairie Meadows race.</p>');
    window.scrollTo({ top: document.querySelector(".content-intro").offsetTop - 20, behavior: "smooth" });
  }
  function prepareJson() {
    try {
      $("json-editor").value = JSON.stringify(buildProblem(), null, 2);
    } catch (e) {
      // A valid editing scaffold is still useful when the form has no offers yet.
      const scaffold = {
        horses: state.horses.map((h) => h.number.trim()).filter(Boolean),
        budget: state.budget,
        stake_rules: state.rules,
        offers: []
      };
      $("json-editor").value = JSON.stringify(scaffold, null, 2);
    }
    $("error-area").hidden = true;
  }

  function bindEvents() {
    $("track-select").addEventListener("change", (e) => {
      state.trackId = e.target.value;
      state.rules = rulesFor(track());
      state.pools.forEach((p) => { p.takeout = track().takeout[p.market] || ""; });
      renderAll(); markDirty();
    });
    $("budget").addEventListener("input", (e) => { state.budget = e.target.value; markDirty(); });
    $("race-number").addEventListener("input", (e) => { state.raceNumber = e.target.value; });
    $("add-horse").addEventListener("click", () => {
      let i = 1; while (state.horses.some((h) => h.number === String(i))) i++;
      state.horses.push(newHorse(i)); renderRunners(); renderPools(); renderOffers(); markDirty();
    });
    $("runners-list").addEventListener("input", (e) => {
      const h = state.horses.find((h) => h.uid === e.target.closest("[data-horse]")?.dataset.horse);
      if (!h || !["number", "name"].includes(e.target.dataset.field)) return;
      h[e.target.dataset.field] = e.target.value; markDirty();
    });
    $("runners-list").addEventListener("change", () => { renderPools(); renderOffers(); });
    $("runners-list").addEventListener("click", (e) => {
      const target = e.target.closest("[data-action=remove-horse]"); if (!target) return;
      if (state.horses.length <= 2) { showError("A race needs at least two runners."); return; }
      const id = target.dataset.id;
      state.horses = state.horses.filter((h) => h.uid !== id);
      state.pools.forEach((p) => { delete p.amounts[id]; });
      state.offers.forEach((o) => {
        o.selection = o.selection.filter((s) => s !== id);
        for (const h of state.horses) { if (o.selection.length >= DEPTH[o.market]) break; if (!o.selection.includes(h.uid)) o.selection.push(h.uid); }
      });
      renderRunners(); renderPools(); renderOffers(); markDirty();
    });
    $("add-pool").addEventListener("click", () => {
      const nextMarket = POOL_MARKETS.find((m) => !state.pools.some((p) => p.market === m)) || "win";
      state.pools.push(newPool(nextMarket)); renderPools(); renderOffers(); markDirty();
    });
    $("pools-list").addEventListener("input", (e) => {
      const pool = state.pools.find((p) => p.uid === e.target.closest("[data-pool]")?.dataset.pool);
      if (!pool) return;
      if (e.target.dataset.field === "takeout") pool.takeout = e.target.value;
      const h = e.target.dataset.amountHorse;
      if (h) {
        pool.amounts[h] = e.target.value;
        e.target.closest(".pool-card").querySelector('[data-role="total"]').textContent = `Total ${showMoney(handleTotal(pool))}`;
      }
      markDirty();
    });
    $("pools-list").addEventListener("change", (e) => {
      const pool = state.pools.find((p) => p.uid === e.target.closest("[data-pool]")?.dataset.pool);
      if (pool && e.target.dataset.field === "market") {
        pool.market = e.target.value;
        pool.id = `${pool.market}-${pool.uid}`;
        pool.takeout = track().takeout[pool.market] || "";
        pool.amounts = {};
        renderPools(); renderOffers(); markDirty();
      }
    });
    $("pools-list").addEventListener("click", (e) => {
      const button = e.target.closest("[data-action]"); if (!button) return;
      const pool = state.pools.find((p) => p.uid === button.dataset.id);
      if (!pool) return;
      if (button.dataset.action === "remove-pool") {
        state.pools = state.pools.filter((p) => p.uid !== pool.uid);
        state.offers.forEach((o) => { if (o.poolUid === pool.uid) { o.source = "fixed"; o.poolUid = ""; } });
      } else if (button.dataset.action === "add-pool-offers") {
        state.horses.forEach((h) => {
          const offer = newOffer(pool.market, "pool");
          offer.selection = [h.uid]; offer.poolUid = pool.uid;
          offer.id = `${pool.market}-${h.number}-${offer.uid}`;
          state.offers.push(offer);
        });
      }
      renderPools(); renderOffers(); markDirty();
    });
    $("add-offer").addEventListener("click", () => { state.offers.push(newOffer()); renderOffers(); markDirty(); });
    $("add-all-win").addEventListener("click", () => {
      state.horses.forEach((h) => {
        const o = newOffer("win"); o.id = `win-${h.number}-${o.uid}`; o.selection = [h.uid]; state.offers.push(o);
      }); renderOffers(); markDirty();
    });
    $("offers-list").addEventListener("input", (e) => {
      const o = state.offers.find((o) => o.uid === e.target.closest("[data-offer]")?.dataset.offer);
      if (!o || !["odds", "book", "maxStake"].includes(e.target.dataset.field)) return;
      o[e.target.dataset.field] = e.target.value; markDirty();
    });
    $("offers-list").addEventListener("change", (e) => {
      const o = state.offers.find((o) => o.uid === e.target.closest("[data-offer]")?.dataset.offer);
      if (!o) return;
      if (e.target.hasAttribute("data-selection-index")) {
        o.selection[Number(e.target.dataset.selectionIndex)] = e.target.value;
      } else if (["market", "source", "oddsType", "poolUid"].includes(e.target.dataset.field)) {
        o[e.target.dataset.field] = e.target.value;
        if (e.target.dataset.field === "market") {
          o.selection = state.horses.slice(0, DEPTH[o.market]).map((h) => h.uid);
          o.poolUid = state.pools.find((p) => p.market === o.market)?.uid || "";
        }
        if (e.target.dataset.field === "source" && o.source === "pool") {
          o.poolUid = state.pools.find((p) => p.market === o.market)?.uid || "";
        }
        renderOffers();
      }
      markDirty();
    });
    $("offers-list").addEventListener("click", (e) => {
      const button = e.target.closest("[data-action=remove-offer]"); if (!button) return;
      state.offers = state.offers.filter((o) => o.uid !== button.dataset.id);
      renderOffers(); markDirty();
    });
    $("stake-rules-list").addEventListener("input", (e) => {
      const market = e.target.closest("[data-market]")?.dataset.market;
      if (market && ["minimum", "increment"].includes(e.target.dataset.field)) { state.rules[market][e.target.dataset.field] = e.target.value; markDirty(); }
    });
    $("stake-rules-list").addEventListener("change", (e) => {
      const market = e.target.closest("[data-market]")?.dataset.market;
      if (market && e.target.dataset.field === "increment_mode") { state.rules[market].increment_mode = e.target.value; markDirty(); }
    });
    $("json-details").addEventListener("toggle", (e) => {
      if (e.target.open && !$("use-json").checked && !$("json-editor").value.trim()) prepareJson();
    });
    $("refresh-json").addEventListener("click", () => { prepareJson(); markDirty(); });
    $("copy-json").addEventListener("click", async () => {
      if (!$("json-editor").value.trim()) prepareJson();
      try { await navigator.clipboard.writeText($("json-editor").value); $("copy-json").textContent = "Copied"; setTimeout(() => { $("copy-json").textContent = "Copy JSON"; }, 1500); }
      catch { showError("Clipboard access is unavailable. Select the JSON text and copy it manually."); }
    });
    $("json-editor").addEventListener("input", () => { if ($("use-json").checked) markDirty(); });
    $("use-json").addEventListener("change", () => { if ($("use-json").checked && !$("json-editor").value.trim()) prepareJson(); markDirty(); });
    $("sample-btn").addEventListener("click", demo);
    $("reset-btn").addEventListener("click", () => {
      state = initialState(); $("use-json").checked = false; $("json-editor").value = ""; renderAll(); resetResults();
    });
    $("race-form").addEventListener("submit", calculate);
  }

  state = initialState();
  bindEvents();
  renderAll();
})();
