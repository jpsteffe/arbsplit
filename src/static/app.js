(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const MARKETS = ["win", "place", "show", "exacta", "quinella", "trifecta", "superfecta"];
  const SIMPLE_MARKETS = ["win", "place", "show"];
  const MARKET_BLURB = {
    win: "to win (finish 1st)",
    place: "to place (finish 1st or 2nd)",
    show: "to show (finish in the top 3)"
  };
  const ODDS_EXAMPLES = { american: "+400", decimal: "5.00", fractional: "4/1" };
  const TRACKS = window.TRACK_PRESETS;
  let sequence = 0;
  let state;
  let hasResults = false;

  const uid = () => `horse-${++sequence}`;
  const html = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  const marketName = (m) => m.charAt(0).toUpperCase() + m.slice(1);
  const track = () => TRACKS.find((t) => t.id === state.trackId) || TRACKS[0];
  const option = (value, label, chosen) => `<option value="${html(value)}" ${value === chosen ? "selected" : ""}>${html(label)}</option>`;

  /* ---------- number helpers ---------- */
  function cents(value, label, allowZero = false) {
    const v = String(value ?? "").trim().replace(/^\$/, "");
    if (!/^(0|[1-9]\d*)(\.\d{1,2})?$/.test(v)) throw new Error(`${label}: enter a dollar amount such as 100 or 12.50 (no commas).`);
    const [whole, dec = ""] = v.split(".");
    const n = Number(whole) * 100 + Number(dec.padEnd(2, "0"));
    if (!Number.isSafeInteger(n) || n < 0 || (!allowZero && n === 0)) throw new Error(`${label}: enter an amount greater than zero.`);
    return n;
  }
  function money(value, label, allowZero = false) {
    const n = cents(value, label, allowZero);
    return `${Math.floor(n / 100)}.${String(n % 100).padStart(2, "0")}`;
  }
  function showMoney(str) {
    const [whole, dec = "00"] = String(str).split(".");
    const neg = whole.startsWith("-");
    const digits = neg ? whole.slice(1) : whole;
    return `${neg ? "-" : ""}$${Number(digits).toLocaleString("en-US")}.${dec.padEnd(2, "0")}`;
  }

  /* ---------- odds parsing (turns what a person typed into optimizer input) ---------- */
  function parseOdds(text, format, label) {
    const t = String(text).trim();
    if (format === "american") {
      if (!/^[+-]?\d{1,6}$/.test(t) || Number(t) === 0) throw new Error(`${label}: odds look like +400 or -110.`);
      const n = Number(t);
      if (Math.abs(n) < 100) throw new Error(`${label}: American odds are +100 or higher, or -100 or lower (for example +250 or -120).`);
      return { american_odds: n };
    }
    if (format === "decimal") {
      if (!/^\d{1,4}(\.\d{1,4})?$/.test(t) || !(Number(t) > 1)) throw new Error(`${label}: decimal odds are bigger than 1, such as 3.50 or 5.00.`);
      return { decimal_odds: t };
    }
    const m = t.match(/^(\d{1,3})\s*(?:\/|-|:|to)\s*(\d{1,3})$/i);
    if (!m || Number(m[1]) === 0 || Number(m[2]) === 0) throw new Error(`${label}: fractional odds look like 4/1 or 5/2.`);
    // "a to b" pays a/b profit per dollar, so the decimal payout is 1 + a/b. Round down, never up.
    const scaled = Math.floor(((Number(m[1]) + Number(m[2])) * 10000) / Number(m[2]));
    if (scaled <= 10000) throw new Error(`${label}: those odds pay out less than your stake.`);
    const whole = Math.floor(scaled / 10000);
    const frac = String(scaled % 10000).padStart(4, "0").replace(/0+$/, "");
    return { decimal_odds: frac ? `${whole}.${frac}` : `${whole}.0` };
  }

  /* ---------- state ---------- */
  function rulesFor(t) {
    return Object.fromEntries(MARKETS.map((m) => [m, {
      minimum: t.minimums[m] || "1.00",
      increment: t.minimums[m] || "1.00",
      increment_mode: "multiples"
    }]));
  }
  function newHorse(number, name = "", win = "", place = "", show = "") {
    return { uid: uid(), number: String(number), name, win, place, show };
  }
  function initialState() {
    return {
      trackId: "PRM", budget: "100", format: "american", usePlaceShow: false,
      horses: Array.from({ length: 4 }, (_, i) => newHorse(i + 1)),
      rules: rulesFor(TRACKS[0])
    };
  }
  function horseLabel(h) { return `#${h.number || "?"}${h.name.trim() ? ` ${h.name.trim()}` : ""}`; }

  /* ---------- status / results housekeeping ---------- */
  function setStatus(text, type = "") {
    $("result-status").textContent = text;
    $("result-status").className = `status ${type}`.trim();
  }
  function markDirty() {
    if (hasResults) setStatus("Out of date", "loading");
  }
  function resetResults() {
    hasResults = false;
    setStatus("Ready");
    $("error-area").hidden = true;
    $("results-content").innerHTML = `<div class="placeholder"><p class="placeholder-title">Nothing calculated yet</p><p>Enter your budget and the odds, then press <strong>Find my bets</strong>.</p><p>Want to see how it works first? Press <strong>Try an example</strong>.</p></div>`;
  }
  function showError(message) {
    $("error-area").textContent = String(message);
    $("error-area").hidden = false;
    setStatus("Needs attention", "error");
  }

  /* ---------- rendering the form ---------- */
  function renderForm() {
    $("budget").value = state.budget;
    $("odds-format").value = state.format;
    $("use-place-show").checked = state.usePlaceShow;
    document.getElementById("odds-table").classList.toggle("show-extra", state.usePlaceShow);
    renderHorses();
    renderTrack();
    renderRules();
  }
  function renderHorses() {
    const ph = ODDS_EXAMPLES[state.format];
    const cell = (h, field, label) => `<td class="col-odds${field === "win" ? "" : " col-extra"}"><input aria-label="${html(label)} for ${html(horseLabel(h))}" data-field="${field}" type="text" inputmode="${state.format === "fractional" ? "text" : "decimal"}" value="${html(h[field])}" placeholder="e.g. ${html(ph)}" autocomplete="off"></td>`;
    $("horses-list").innerHTML = state.horses.map((h) => `<tr data-horse="${html(h.uid)}">
      <td class="col-num"><input aria-label="Horse number" class="num-input" data-field="number" type="text" maxlength="6" value="${html(h.number)}" autocomplete="off"></td>
      <td class="col-name"><input aria-label="Horse name for number ${html(h.number)}" data-field="name" type="text" maxlength="60" value="${html(h.name)}" placeholder="optional" autocomplete="off"></td>
      ${cell(h, "win", "Win odds")}${cell(h, "place", "Place odds")}${cell(h, "show", "Show odds")}
      <td class="col-del"><button type="button" class="icon-button" title="Remove this horse" aria-label="Remove ${html(horseLabel(h))}" data-action="remove-horse" data-id="${html(h.uid)}">×</button></td>
    </tr>`).join("");
  }
  function renderTrack() {
    $("track-select").innerHTML = TRACKS.map((t) => option(t.id, `${t.name} — ${t.location}`, state.trackId)).join("");
    const t = track();
    $("preset-info").innerHTML = `<p>${html(t.note)}</p>${t.sources.length ? `<div class="source-links">${t.sources.map((s) => `<a href="${html(s.url)}" target="_blank" rel="noopener noreferrer">${html(s.label)} ↗</a>`).join("")}</div>` : ""}`;
  }
  function renderRules() {
    $("stake-rules-list").innerHTML = SIMPLE_MARKETS.map((m) => `<label class="field"><span>Smallest ${m} bet</span><div class="input-prefix"><span>$</span><input type="text" inputmode="decimal" data-market="${m}" value="${html(state.rules[m].minimum)}"></div></label>`).join("");
  }

  /* ---------- form -> optimizer problem ---------- */
  function buildProblem() {
    if (state.horses.length < 2) throw new Error("Add at least two horses.");
    const numbers = state.horses.map((h) => h.number.trim());
    if (numbers.some((v) => !v)) throw new Error("Every horse needs a number.");
    if (new Set(numbers).size !== numbers.length) throw new Error("Two horses have the same number. Each horse needs its own number.");

    const rules = {};
    for (const m of MARKETS) {
      const r = state.rules[m];
      rules[m] = { minimum: money(r.minimum, `Smallest ${m} bet`), increment: money(r.increment, `Smallest ${m} bet`), increment_mode: r.increment_mode };
    }

    const markets = state.usePlaceShow ? SIMPLE_MARKETS : ["win"];
    const offers = [];
    for (const h of state.horses) {
      for (const m of markets) {
        const text = h[m].trim();
        if (!text) continue;
        const odds = parseOdds(text, state.format, `${horseLabel(h)} ${m} odds`);
        offers.push({ id: `${m}-${h.number.trim()}`, market: m, selection: [h.number.trim()], ...odds });
      }
    }
    if (!offers.length) throw new Error("Enter odds for at least one horse first (or press “Try an example”).");

    return {
      horses: numbers, budget: money(state.budget, "Budget"),
      race_rules: { place_pays_top: Math.min(2, numbers.length), show_pays_top: Math.min(3, numbers.length) },
      stake_rules: rules, offers
    };
  }

  /* ---------- rendering results ---------- */
  function describeBet(b, nameMap) {
    const horse = (n) => `#${n}${nameMap[n] ? ` ${nameMap[n]}` : ""}`;
    const sel = b.selection || [];
    if (SIMPLE_MARKETS.includes(b.market)) return { who: horse(sel[0]), what: MARKET_BLURB[b.market] };
    const order = b.market === "quinella" ? " and " : " then ";
    return { who: sel.map(horse).join(order), what: `${b.market} bet` };
  }
  function renderBets(result, nameMap, oddsText) {
    return `<ol class="bet-list">${(result.selected_bets || []).map((b) => {
      const d = describeBet(b, nameMap);
      const typed = oddsText[b.id];
      const detail = b.pool_id
        ? `Pays between ${showMoney(b.minimum_payout_if_wins)} and ${showMoney(b.maximum_payout_if_wins)} if it wins`
        : `At odds of ${html(typed || b.odds)}, you get ${showMoney(b.payout_if_wins)} back if it wins`;
      return `<li class="bet"><div class="bet-main"><span class="bet-stake">${showMoney(b.stake)}</span><span class="bet-text">on <strong>${html(d.who)}</strong> ${html(d.what)}</span></div><div class="bet-detail">${detail}</div></li>`;
    }).join("")}</ol>`;
  }
  function renderResults(results) {
    const nameMap = Object.fromEntries(state.horses.map((h) => [h.number.trim(), h.name.trim()]));
    const oddsText = {};
    for (const h of state.horses) for (const m of SIMPLE_MARKETS) if (h[m].trim()) oddsText[`${m}-${h.number.trim()}`] = h[m].trim();

    const best = results.max_profit || results.min_bets;
    const fewest = results.min_bets;
    const found = best.status === "optimal_arbitrage";
    let out = "";

    if (found) {
      const spend = showMoney(best.total_staked);
      out += `<div class="verdict good">
        <div class="verdict-title">Profit found</div>
        <div class="verdict-amount">${showMoney(best.guaranteed_profit)}</div>
        <p>If you place the bets below, you finish at least this much ahead <strong>no matter which horse wins</strong>.</p>
      </div>
      <h3>Place these bets</h3>
      ${renderBets(best, nameMap, oddsText)}
      <div class="summary-row"><div><span>You spend</span><strong>${spend}</strong></div><div><span>Worst case you get back</span><strong>${showMoney(best.minimum_payout)}</strong></div></div>`;

      if (results.max_profit && fewest && fewest.status === "optimal_arbitrage" && fewest.number_of_bets < best.number_of_bets) {
        out += `<details class="alt-plan"><summary>Prefer fewer bets?</summary>
          <p>This plan uses only <strong>${html(fewest.number_of_bets)}</strong> ${fewest.number_of_bets === 1 ? "bet" : "bets"} and still guarantees at least <strong>${showMoney(fewest.guaranteed_profit)}</strong> profit.</p>
          ${renderBets(fewest, nameMap, oddsText)}
        </details>`;
      }
    } else {
      out += `<div class="verdict none">
        <div class="verdict-title">No sure profit with these odds</div>
        <p>That's common. A guaranteed profit only exists when the odds you can get disagree enough, for example when one site offers noticeably better odds on a horse than another.</p>
        <p>Double-check the odds you typed, or add odds from another source and try again.</p>
      </div>`;
    }
    $("results-content").innerHTML = out;
    setStatus("Done", "done");
    $("error-area").hidden = true;
    hasResults = true;
  }

  /* ---------- calculation ---------- */
  async function calculate(event) {
    event?.preventDefault();
    const button = $("run-btn");
    if (button.disabled) return;
    let problem;
    try {
      problem = $("use-json").checked ? JSON.parse($("json-editor").value) : buildProblem();
    } catch (e) {
      showError(e instanceof SyntaxError ? `The JSON isn't valid: ${e.message}` : e.message);
      return;
    }
    const payload = {
      problem, mode: "both",
      minimum_profit: $("minimum-profit").value.trim(),
      tie_break: "max_profit",
      time_limit: Number($("time-limit").value)
    };
    try {
      payload.minimum_profit = money(payload.minimum_profit, "Smallest profit worth reporting");
      if (!Number.isFinite(payload.time_limit) || payload.time_limit <= 0 || payload.time_limit > 60) throw new Error("“Give up after” must be between 1 and 60 seconds.");
      button.disabled = true;
      $("run-button-label").textContent = "Working…";
      setStatus("Working…", "loading");
      $("error-area").hidden = true;
      const response = await fetch("/api/calculate", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload)
      });
      const data = await response.json();
      if (!response.ok) {
        const detail = data.detail;
        throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
      }
      renderResults(data.results);
      if (window.matchMedia("(max-width: 850px)").matches) $("results-title").scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (e) {
      showError(e.message || "Something went wrong. Please check your inputs.");
    } finally {
      button.disabled = false;
      $("run-button-label").textContent = "Find my bets";
    }
  }

  /* ---------- example / JSON ---------- */
  function demo() {
    state = initialState();
    state.format = "american";
    state.horses = [
      newHorse("1", "Sample A", "+300"),
      newHorse("2", "Sample B", "+250"),
      newHorse("3", "Sample C", "+200")
    ];
    $("use-json").checked = false;
    renderForm(); resetResults();
    $("race-form").scrollIntoView({ behavior: "smooth", block: "start" });
    $("results-content").innerHTML = `<div class="placeholder"><p class="placeholder-title">Example loaded</p><p>These horses and odds are made up. Press <strong>Find my bets</strong> to see what the calculator does with them.</p></div>`;
  }
  function prepareJson() {
    try {
      $("json-editor").value = JSON.stringify(buildProblem(), null, 2);
    } catch (e) {
      $("json-editor").value = JSON.stringify({
        horses: state.horses.map((h) => h.number.trim()).filter(Boolean),
        budget: state.budget,
        stake_rules: state.rules,
        offers: []
      }, null, 2);
    }
    $("error-area").hidden = true;
  }

  /* ---------- events ---------- */
  function bindEvents() {
    $("budget").addEventListener("input", (e) => { state.budget = e.target.value; markDirty(); });
    $("odds-format").addEventListener("change", (e) => { state.format = e.target.value; renderHorses(); markDirty(); });
    $("use-place-show").addEventListener("change", (e) => {
      state.usePlaceShow = e.target.checked;
      $("odds-table").classList.toggle("show-extra", state.usePlaceShow);
      markDirty();
    });
    $("add-horse").addEventListener("click", () => {
      let i = 1; while (state.horses.some((h) => h.number === String(i))) i++;
      state.horses.push(newHorse(i)); renderHorses(); markDirty();
      $("horses-list").querySelector("tr:last-child [data-field=win]")?.focus();
    });
    $("horses-list").addEventListener("input", (e) => {
      const h = state.horses.find((h) => h.uid === e.target.closest("[data-horse]")?.dataset.horse);
      const field = e.target.dataset.field;
      if (!h || !["number", "name", "win", "place", "show"].includes(field)) return;
      h[field] = e.target.value; markDirty();
    });
    $("horses-list").addEventListener("click", (e) => {
      const target = e.target.closest("[data-action=remove-horse]"); if (!target) return;
      if (state.horses.length <= 2) { showError("A race needs at least two horses."); return; }
      state.horses = state.horses.filter((h) => h.uid !== target.dataset.id);
      renderHorses(); markDirty();
    });
    $("track-select").addEventListener("change", (e) => {
      state.trackId = e.target.value;
      state.rules = rulesFor(track());
      renderTrack(); renderRules(); markDirty();
    });
    $("stake-rules-list").addEventListener("input", (e) => {
      const m = e.target.dataset.market; if (!m) return;
      state.rules[m].minimum = e.target.value;
      state.rules[m].increment = e.target.value;
      markDirty();
    });
    $("advanced-details").addEventListener("input", (e) => {
      if (["minimum-profit", "time-limit", "json-editor"].includes(e.target.id)) markDirty();
    });
    $("refresh-json").addEventListener("click", () => { prepareJson(); markDirty(); });
    $("copy-json").addEventListener("click", async () => {
      if (!$("json-editor").value.trim()) prepareJson();
      try { await navigator.clipboard.writeText($("json-editor").value); $("copy-json").textContent = "Copied"; setTimeout(() => { $("copy-json").textContent = "Copy"; }, 1500); }
      catch { showError("Couldn't access the clipboard. Select the JSON text and copy it manually."); }
    });
    $("use-json").addEventListener("change", () => { if ($("use-json").checked && !$("json-editor").value.trim()) prepareJson(); markDirty(); });
    $("sample-btn").addEventListener("click", demo);
    $("reset-btn").addEventListener("click", () => {
      state = initialState(); $("use-json").checked = false; $("json-editor").value = ""; renderForm(); resetResults();
    });
    $("race-form").addEventListener("submit", calculate);
  }

  state = initialState();
  bindEvents();
  renderForm();
})();
