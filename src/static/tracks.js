/*
 * Editable starting values, NOT a live tote feed and NOT settlement rules.
 * Takeout: independently compiled 2026 table (Nov 23, 2026).
 * Sources: https://inthemoneypodcast.com/horse-racing-takeout-rates/
 * PRM wager denominations: track guide, Iowa rules, and Equibase Sept 2026 charts.
 * Exotic minimums vary by venue, program and operator; VERIFY before use.
 */
window.TRACK_PRESETS = Object.freeze([
  {
    id: "PRM",
    name: "Prairie Meadows",
    location: "Altoona, Iowa",
    short: "PRM · ALTOONA, IA",
    takeout: { win: "17", place: "17", show: "17", exacta: "20", quinella: "20", trifecta: "20", superfecta: "20" },
    minimums: { win: "2.00", place: "2.00", show: "2.00", exacta: "2.00", quinella: "2.00", trifecta: "0.50", superfecta: "0.10" },
    note: "W/P/S $2 from Iowa rules and the track guide. 2026 charts use $0.50 trifecta, $0.10 superfecta and $2 exacta/quinella payoff bases; a published payoff base is not necessarily a minimum stake. Confirm exacta/quinella minimums and availability at the window. Takeout rates are independent estimates, not official current quotes.",
    sources: [
      { label: "Prairie Meadows wagering guide", url: "https://www.prairiemeadows.com/community/articles/blog/wagering-101" },
      { label: "Iowa minimum-wager rules", url: "https://rules.iowa.gov/Notice/Details/0186D" },
      { label: "PRM 2026 results / denominations", url: "https://tvg.equibase.com/static/chart/summary/PRM092526USA3-EQB.html" },
      { label: "Takeout comparison (Nov 2026)", url: "https://inthemoneypodcast.com/horse-racing-takeout-rates/" }
    ]
  },
  {
    id: "OP",
    name: "Oaklawn Park",
    location: "Hot Springs, Arkansas",
    short: "OP · HOT SPRINGS, AR",
    takeout: { win: "17", place: "17", show: "17", exacta: "21", quinella: "", trifecta: "21", superfecta: "21" },
    minimums: { win: "2.00", place: "2.00", show: "2.00", exacta: "1.00", quinella: "1.00", trifecta: "1.00", superfecta: "0.10" },
    note: "Takeout rates are November 2026 independent estimates. Wager minimums here are editable starting assumptions, not confirmed Oaklawn-specific rules. Quinella takeout is deliberately blank until verified.",
    sources: [
      { label: "Takeout comparison (Nov 2026)", url: "https://inthemoneypodcast.com/horse-racing-takeout-rates/" }
    ]
  },
  {
    id: "KEE",
    name: "Keeneland",
    location: "Lexington, Kentucky",
    short: "KEE · LEXINGTON, KY",
    takeout: { win: "16", place: "16", show: "16", exacta: "19.5", quinella: "", trifecta: "22", superfecta: "22" },
    minimums: { win: "2.00", place: "2.00", show: "2.00", exacta: "1.00", quinella: "1.00", trifecta: "1.00", superfecta: "0.10" },
    note: "Takeout rates are November 2026 independent estimates. Wager minimums here are editable starting assumptions, not confirmed Keeneland-specific rules. Quinella takeout is deliberately blank until verified.",
    sources: [
      { label: "Takeout comparison (Nov 2026)", url: "https://inthemoneypodcast.com/horse-racing-takeout-rates/" }
    ]
  },
  {
    id: "CUSTOM",
    name: "Custom track",
    location: "Enter your own rules",
    short: "CUSTOM RACE",
    takeout: { win: "", place: "", show: "", exacta: "", quinella: "", trifecta: "", superfecta: "" },
    minimums: { win: "1.00", place: "1.00", show: "1.00", exacta: "1.00", quinella: "1.00", trifecta: "1.00", superfecta: "1.00" },
    note: "Enter and verify all wager minimums, increments and pool takeout rates for this track.",
    sources: []
  }
]);
