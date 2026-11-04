/* River Azoth guide: shared chrome plus the data views. Static site, no build step: the JSON in data/ comes from scripts/guide_data.py. */
(function () {
  "use strict";
  const NAV = [["index.html", "Guide"], ["start.html", "Start"], ["walkthrough.html", "Johto"], ["river.html", "River Edition"],
    ["trainers.html", "Trainers"], ["pokedex.html", "Pokédex"], ["moves.html", "Moves"], ["items.html", "Items"], ["locations.html", "Wild Pokémon"]];
  const $ = (s, r) => (r || document).querySelector(s);
  const el = (t, a, ...k) => {
    const e = document.createElement(t);
    for (const [n, v] of Object.entries(a || {})) { if (n === "html") e.innerHTML = v; else if (n === "class") e.className = v; else e.setAttribute(n, v); }
    for (const c of k.flat()) if (c != null) e.append(c.nodeType ? c : document.createTextNode(c));
    return e;
  };
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const store = { get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }, set(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* private mode */ } } };

  /* ---------- chrome ---------- */
  function chrome() {
    const lk = document.createElement("link");
    lk.rel = "stylesheet";
    lk.href = "https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@62..125,500..900&family=Source+Sans+3:ital,wght@0,400..700;1,400&family=IBM+Plex+Mono:wght@400;600&display=swap";
    document.head.append(lk);
    const t = store.get("guide-theme");
    if (t) document.documentElement.dataset.theme = t;
    const here = location.pathname.split("/").pop() || "index.html";
    const nav = el("nav", { "aria-label": "Guide sections" }, NAV.map(([h, n]) => {
      const a = el("a", { href: h }, n);
      if (h === here) a.setAttribute("aria-current", "page");
      return a;
    }));
    const btn = el("button", { type: "button", title: "Switch light and dark" }, "Light/Dark");
    btn.onclick = () => {
      const dark = getComputedStyle(document.body).backgroundColor.match(/\d+/g).map(Number).reduce((a, b) => a + b, 0) < 300;
      const nx = dark ? "light" : "dark";
      document.documentElement.dataset.theme = nx; store.set("guide-theme", nx);
    };
    document.body.prepend(el("header", { class: "bar" }, el("div", { class: "wrap" }, el("a", { class: "brand", href: "index.html" }, "River Azoth"), nav, btn)), el("div", { class: "stripe" }));
    const b = document.body.dataset;
    const head = el("div", { class: "head" }, el("div", { class: "wrap" }, el("div", { class: "n" }, b.kicker || ""), el("h1", {}, b.title || document.title), b.lede ? el("p", {}, b.lede) : null));
    $("main").before(head);
    document.body.append(el("footer", { class: "site" }, el("div", { class: "stripe", style: "margin:-1.6rem 0 1.4rem" }), el("div", { class: "wrap" },
      el("p", { html: "<b>Unofficial fan guide.</b> This is a translation done with Claude plus fan-made additions by River. <i>Pokémon Azoth</i> (口袋妖怪 水银, &ldquo;Mercury&rdquo;), its characters and its story belong to their original authors; Pokémon is a trademark of its owners. Nothing here is affiliated with or endorsed by them, and no ROMs are distributed. Data tables are read straight from the patched ROM (<code>scripts/guide_data.py</code>). For the original Chinese-language reference see the <a href=\"https://sum-light.github.io/azoth-wiki/\">Pokémon Mercury wiki</a>." }),
      el("p", { html: "Found a mistake? <a href=\"https://github.com/RiFa-Innovation/pkmn-azoth-translation/issues/new/choose\">Open an issue</a>." }))));
  }

  /* ---------- data ---------- */
  const cache = {};
  const load = n => cache[n] || (cache[n] = fetch("data/" + n + ".json").then(r => { if (!r.ok) throw new Error(n); return r.json(); }));
  let TYPES = [];
  const tyn = i => TYPES[i] || "???";
  const ty = i => el("span", { class: "ty", "data-t": tyn(i) }, tyn(i));
  const STAT = ["HP", "Atk", "Def", "Spe", "SpA", "SpD"];
  const STATORD = [0, 1, 2, 4, 5, 3];
  const SPLIT = ["Physical", "Special", "Status"];
  const EVO = { 1: "friendship", 2: "friendship (day)", 3: "friendship (night)", 4: "level ", 5: "trade", 6: "trade holding ", 7: "use ", 8: "level (Atk > Def) ", 9: "level (Atk = Def) ", 10: "level (Atk < Def) ", 11: "level (Silcoon) ", 12: "level (Cascoon) ", 13: "level (Ninjask) ", 14: "level (Shedinja) ", 15: "beauty " };
  let DUP = null;
  const mon = (S, id) => {
    if (!S[id]) return "#" + id;
    if (!DUP) { DUP = {}; Object.values(S).sort((a, b) => a.id - b.id).forEach(s => { (DUP[s.name] = DUP[s.name] || []).push(s.id); }); }
    const d = DUP[S[id].name];
    return d.length > 1 && d[0] !== +id ? S[id].name + " (form #" + id + ")" : S[id].name;
  };

  function evoText(S, M, I, e) {
    const [m, p, to] = e;
    const label = EVO[m];
    let txt;
    if (m === 254) txt = "Mega Evolution, holding " + ((I[p] || {}).name || "a Mega Stone");
    else if (m === 253) txt = "form change";
    else if (label === undefined) txt = "special condition (method " + m + ", value " + p + ")";
    else if (m === 7 || m === 6) txt = label + ((I[p] || {}).name || "item " + p);
    else if (m >= 4 && m !== 5 && m <= 15) txt = label + p;
    else txt = label;
    return [to, txt];
  }

  /* ---------- Pokédex ---------- */
  async function pokedex() {
    const [D, M, I, W] = await Promise.all([load("species"), load("moves"), load("items"), load("wild")]);
    TYPES = D.types;
    const S = D.species, A = D.abilities;
    const list = Object.values(S).sort((a, b) => a.id - b.id);
    const root = $("#view");
    const q = el("input", { type: "search", id: "q", placeholder: "Name, number or ability", "aria-label": "Search Pokémon" });
    const tf = el("select", { id: "tf", "aria-label": "Type" }, el("option", { value: "" }, "Any type"), D.types.filter(t => t !== "???").map((t, i) => el("option", { value: String(D.types.indexOf(t)) }, t)));
    const cnt = el("span", { class: "count" });
    const tbody = el("tbody");
    const sorts = { id: (a, b) => a.id - b.id, name: (a, b) => a.name.localeCompare(b.name), bst: (a, b) => bst(b) - bst(a) };
    let sort = "id";
    const bst = s => s.stats.reduce((a, b) => a + b, 0);
    const head = el("tr", {}, [["id", "No."], ["name", "Name"], [null, "Types"], [null, "Abilities"], ["bst", "Total"]].map(([k, n]) => {
      const th = el("th", n === "bst" || n === "No." ? { class: "num" } : {}, n);
      if (k) { th.dataset.sort = k; th.onclick = () => { sort = k; draw(); }; th.title = "Sort"; }
      return th;
    }));
    const wrap = el("div", { class: "tw" }, el("table", {}, el("thead", {}, head), tbody));
    const detail = el("div", { id: "detail" });
    root.append(el("div", { class: "tools" }, q, tf, cnt), detail, wrap);
    function draw() {
      const term = q.value.trim().toLowerCase(), t = tf.value;
      let rows = list.filter(s => (!t || s.types.includes(+t)) &&
        (!term || s.name.toLowerCase().includes(term) || String(s.id) === term || s.abil.some(a => (A[a] || "").toLowerCase().includes(term)))).sort(sorts[sort]);
      cnt.textContent = rows.length + " of " + list.length;
      tbody.replaceChildren(...rows.slice(0, 400).map(s => {
        const a = el("a", { href: "#" + s.id }, mon(S, s.id));
        return el("tr", {}, el("td", { class: "num" }, s.id), el("td", {}, a), el("td", {}, s.types.map(ty)), el("td", {}, s.abil.map(x => A[x] || "?").join(", ")), el("td", { class: "num" }, bst(s)));
      }));
      if (rows.length > 400) tbody.append(el("tr", {}, el("td", { colspan: 5 }, "Showing the first 400. Narrow the search.")));
    }
    q.oninput = tf.onchange = draw;
    function show() {
      const id = +location.hash.slice(1);
      detail.replaceChildren();
      if (!S[id]) return;
      const s = S[id];
      const card = el("div", { class: "battle" });
      card.append(el("h3", { style: "margin:0" }, "#" + s.id + " " + mon(S, s.id)), el("div", { class: "mon" }, s.types.map(ty), el("span", {}, "Abilities: " + (s.abil.map(x => A[x] || "?").join(", ") || "none"))));
      const stats = el("div", {});
      STATORD.forEach(i => stats.append(el("div", { class: "stat" }, el("b", {}, STAT[i]), el("span", {}, s.stats[i]), el("div", { class: "tr" }, el("i", { style: "width:" + Math.min(100, s.stats[i] / 2.55) + "%" })))));
      stats.append(el("div", { class: "stat" }, el("b", {}, "Total"), el("span", {}, bst(s)), el("span")));
      const evo = s.evos.map(e => { const [to, t] = evoText(S, M, I, e); return el("li", {}, "→ ", el("a", { href: "#" + to }, mon(S, to)), " (" + t + ")"); });
      const from = list.filter(o => o.evos.some(e => e[2] === s.id)).map(o => el("li", {}, "← ", el("a", { href: "#" + o.id }, mon(S, o.id))));
      const lv = s.learn.map(([l, m]) => el("tr", {}, el("td", { class: "num" }, l === 0 ? "Evo" : l), el("td", {}, M[m] ? el("a", { href: "moves.html#" + m }, M[m].name) : "move " + m), el("td", {}, M[m] ? ty(M[m].type) : ""), el("td", { class: "num" }, M[m] && M[m].power ? M[m].power : "-")));
      const found = W.filter(w => ["land", "water", "rock", "fish"].some(k => w[k] && w[k].mons.some(x => x[0] === s.id)));
      const where = found.map(w => {
        const parts = ["land", "water", "rock", "fish"].filter(k => w[k] && w[k].mons.some(x => x[0] === s.id)).map(k => KIND[k]);
        const lvls = [].concat(...["land", "water", "rock", "fish"].filter(k => w[k]).map(k => w[k].mons.filter(x => x[0] === s.id)));
        const lo = Math.min(...lvls.map(x => x[1])), hi = Math.max(...lvls.map(x => x[2]));
        return el("li", {}, el("a", { href: "locations.html#" + w.map }, w.name), " · " + parts.join(", ") + " · Lv " + (lo === hi ? lo : lo + "-" + hi));
      });
      card.append(el("div", { class: "two" }, stats, el("div", {}, el("h4", {}, "Evolution"), el("ul", {}, from, evo, (!from.length && !evo.length) ? el("li", {}, "None") : null),
        el("h4", {}, "Where to find it"), el("ul", {}, where.length ? where.slice(0, 20) : el("li", {}, "No wild encounter in the tables (gift, evolution, event or Frontier)."))),),
        el("h4", {}, "Learnset"), el("div", { class: "tw" }, el("table", {}, el("thead", {}, el("tr", {}, el("th", { class: "num" }, "Lv"), el("th", {}, "Move"), el("th", {}, "Type"), el("th", { class: "num" }, "Power"))), el("tbody", {}, lv))));
      detail.append(card);
      if (detail.scrollIntoView) detail.scrollIntoView({ block: "nearest" });
    }
    addEventListener("hashchange", show);
    draw(); show();
  }
  const KIND = { land: "grass/cave", water: "surf", rock: "rock smash", fish: "fishing" };

  /* ---------- Moves ---------- */
  async function moves() {
    const [D, M] = await Promise.all([load("species"), load("moves")]);
    TYPES = D.types; const S = D.species;
    const list = Object.values(M).sort((a, b) => a.name.localeCompare(b.name));
    const q = el("input", { type: "search", placeholder: "Move name or description", "aria-label": "Search moves" });
    const tf = el("select", { "aria-label": "Type" }, el("option", { value: "" }, "Any type"), D.types.filter(t => t !== "???").map(t => el("option", { value: String(D.types.indexOf(t)) }, t)));
    const sf = el("select", { "aria-label": "Category" }, el("option", { value: "" }, "Any category"), SPLIT.map((n, i) => el("option", { value: i }, n)));
    const cnt = el("span", { class: "count" }), tbody = el("tbody"), detail = el("div");
    $("#view").append(el("div", { class: "tools" }, q, tf, sf, cnt), detail, el("div", { class: "tw" }, el("table", {}, el("thead", {}, el("tr", {}, ["Move", "Type", "Cat.", "Power", "Acc.", "PP", "Effect"].map((n, i) => el("th", i > 2 && i < 6 ? { class: "num" } : {}, n)))), tbody)));
    function draw() {
      const t = q.value.trim().toLowerCase();
      const rows = list.filter(m => (!tf.value || m.type === +tf.value) && (!sf.value || m.split === +sf.value) && (!t || m.name.toLowerCase().includes(t) || m.desc.toLowerCase().includes(t)));
      cnt.textContent = rows.length + " of " + list.length;
      tbody.replaceChildren(...rows.slice(0, 500).map(m => el("tr", { id: "m" + m.id }, el("td", {}, el("a", { href: "#" + m.id }, m.name)), el("td", {}, ty(m.type)), el("td", {}, SPLIT[m.split]), el("td", { class: "num" }, m.power || "-"), el("td", { class: "num" }, m.acc || "-"), el("td", { class: "num" }, m.pp), el("td", {}, m.desc))));
    }
    q.oninput = tf.onchange = sf.onchange = draw;
    function show() {
      const id = +location.hash.slice(1); detail.replaceChildren();
      const m = M[id]; if (!m) return;
      const lv = [], by = new Map();
      Object.values(S).forEach(s => s.learn.forEach(([l, x]) => { if (x === id) lv.push([s, l]); }));
      detail.append(el("div", { class: "battle" }, el("h3", { style: "margin:0" }, m.name), el("div", { class: "mon" }, ty(m.type), el("span", {}, SPLIT[m.split] + " · Power " + (m.power || "-") + " · Acc " + (m.acc || "-") + " · PP " + m.pp + (m.pri ? " · Priority " + m.pri : ""))), el("p", {}, m.desc),
        el("h4", {}, "Learned by level-up (" + lv.length + ")"), el("p", { style: "max-width:none" }, lv.sort((a, b) => a[0].id - b[0].id).slice(0, 300).map(([s, l], i) => [i ? ", " : "", el("a", { href: "pokedex.html#" + s.id }, s.name), " (" + (l || "evo") + ")"]).flat())));
    }
    addEventListener("hashchange", show); draw(); show();
  }

  /* ---------- Items ---------- */
  const SRC_ORDER = ["Found", "Received", "Script reward", "Shop", "Battle Points shop", "Held by wild Pokémon", "Held by trainers"];
  const SRC_NOTE = { "Found": "Item ball or hidden on the ground", "Received": "Given to you by a script or NPC", "Script reward": "Reward from a quest or event script", "Shop": "Poké Mart stock", "Battle Points shop": "Spectrum Frontier BP clerk", "Held by wild Pokémon": "Chance that a wild one carries it", "Held by trainers": "Carried by these trainers' Pokémon" };
  async function items() {
    const [I, X, M, D] = await Promise.all([load("items"), load("misc"), load("moves"), load("species")]);
    TYPES = D.types;
    const tm = X.tm, P = X.pockets;
    const list = Object.values(I).map(i => {
      const m = /^TM(\d+)$/.exec(i.name) || /^HM(\d+)$/.exec(i.name);
      let mv = null;
      if (m) { const n = +m[1] + (i.name[0] === "H" ? 120 : 0); mv = M[tm[n - 1]] || null; }
      const kinds = [...new Set((i.src || []).map(r => r[0]))];
      return { ...i, mv, move: mv ? mv.name : "", kinds };
    });
    const q = el("input", { type: "search", placeholder: "Item, description or location", "aria-label": "Search items" });
    const pf = el("select", { "aria-label": "Pocket" }, el("option", { value: "" }, "All pockets"), Object.entries(P).map(([k, n]) => el("option", { value: k }, n)));
    const sf = el("select", { "aria-label": "Source" }, el("option", { value: "" }, "Any source"), el("option", { value: "none" }, "No known source"), SRC_ORDER.map(k => el("option", { value: k }, k)));
    const cnt = el("span", { class: "count" }), tbody = el("tbody"), detail = el("div");
    $("#view").append(el("div", { class: "tools" }, q, pf, sf, cnt), detail, el("div", { class: "tw" }, el("table", {}, el("thead", {}, el("tr", {}, ["Item", "Pocket", "Buy", "Where to get it", "Description"].map((n, i) => el("th", i === 2 ? { class: "num" } : {}, n)))), tbody)));
    const blob = i => (i.name + " " + i.move + " " + i.desc + " " + (i.src || []).map(r => r[1].join(" ")).join(" ")).toLowerCase();
    function draw() {
      const t = q.value.trim().toLowerCase();
      const rows = list.filter(i => (!pf.value || i.pocket === +pf.value) && (!sf.value || (sf.value === "none" ? !i.kinds.length : i.kinds.includes(sf.value))) && (!t || blob(i).includes(t)));
      cnt.textContent = rows.length + " of " + list.length;
      tbody.replaceChildren(...rows.slice(0, 800).map(i => el("tr", {}, el("td", {}, el("a", { href: "#" + i.id }, i.name + (i.move ? " (" + i.move + ")" : ""))), el("td", {}, P[i.pocket] || "-"), el("td", { class: "num" }, i.price ? "¥" + i.price : "-"),
        el("td", {}, i.kinds.length ? i.kinds.map(k => k.replace("Held by ", "Held: ").replace("Battle Points shop", "BP shop")).join(", ") : "-"), el("td", {}, i.desc))));
    }
    function show() {
      const id = +location.hash.slice(1); detail.replaceChildren();
      const i = list.find(x => x.id === id); if (!i) return;
      const card = el("div", { class: "battle" }, el("h3", { style: "margin:0" }, i.name), el("div", { class: "sub" }, (P[i.pocket] || "Item") + " · item " + i.id + " · " + (i.price ? "buy ¥" + i.price + ", sell ¥" + Math.floor(i.price / 2) : "not sold in shops")), el("p", {}, i.desc));
      if (i.mv) card.append(el("h4", {}, "Teaches " + i.mv.name), el("div", { class: "mon" }, ty(i.mv.type), el("span", {}, SPLIT[i.mv.split] + " · Power " + (i.mv.power || "-") + " · Acc " + (i.mv.acc || "-") + " · PP " + i.mv.pp)), el("p", {}, i.mv.desc), el("p", {}, el("a", { href: "moves.html#" + i.mv.id }, "Move page and learners")));
      const groups = SRC_ORDER.map(k => [k, (i.src || []).filter(r => r[0] === k)]).filter(g => g[1].length);
      card.append(el("h4", {}, "Where to get it"));
      if (!groups.length) card.append(el("p", {}, "No source was found in the ROM's scripts, shops or held-item tables. It may be a gift made by native code, a Frontier prize or an unused item."));
      groups.forEach(([k, rows]) => card.append(el("div", {}, el("h4", {}, k + " ", el("small", { style: "font-weight:400;color:var(--muted)" }, SRC_NOTE[k])),
        el("ul", {}, rows.slice(0, 40).map(r => el("li", {}, (r[1].length ? r[1].join(" or ") : "location not determined") + (r[2] > 1 && k !== "Shop" ? " ×" + r[2] : "") + (r[3] ? " · " + r[3] + " BP" : "")))))));
      detail.append(card);
      if (detail.scrollIntoView) detail.scrollIntoView({ block: "nearest" });
    }
    q.oninput = pf.onchange = sf.onchange = draw;
    addEventListener("hashchange", show); draw(); show();
  }

  /* ---------- Wild locations ---------- */
  const RATE = { land: [20, 20, 10, 10, 10, 10, 5, 5, 4, 4, 1, 1], water: [60, 30, 5, 4, 1], rock: [60, 30, 5, 4, 1], fish: [70, 30, 60, 20, 20, 40, 40, 15, 4, 1] };
  async function locations() {
    const [W, D] = await Promise.all([load("wild"), load("species")]);
    const S = D.species;
    const q = el("input", { type: "search", placeholder: "Area or Pokémon", "aria-label": "Search areas" });
    const cnt = el("span", { class: "count" }), out = el("div");
    $("#view").append(el("div", { class: "tools" }, q, cnt), out);
    function block(w, k) {
      const b = w[k]; if (!b) return null;
      const agg = new Map();
      b.mons.forEach(([sp, lo, hi], i) => {
        const key = sp + ":" + lo + "-" + hi, r = agg.get(key) || { sp, lo, hi, pct: 0 };
        r.pct += (RATE[k] || [])[i] || 0; agg.set(key, r);
      });
      return el("div", {}, el("h4", {}, KIND[k][0].toUpperCase() + KIND[k].slice(1) + " (encounter rate " + b.rate + ")"),
        el("div", { class: "tw" }, el("table", {}, el("thead", {}, el("tr", {}, el("th", {}, "Pokémon"), el("th", { class: "num" }, "Levels"), el("th", { class: "num" }, "Chance"))),
          el("tbody", {}, [...agg.values()].sort((a, b) => b.pct - a.pct).map(r => el("tr", {}, el("td", {}, el("a", { href: "pokedex.html#" + r.sp }, mon(S, r.sp))), el("td", { class: "num" }, r.lo === r.hi ? r.lo : r.lo + "-" + r.hi), el("td", { class: "num" }, r.pct + "%")))))));
    }
    function draw() {
      const t = q.value.trim().toLowerCase();
      const rows = W.filter(w => !t || w.name.toLowerCase().includes(t) || ["land", "water", "rock", "fish"].some(k => w[k] && w[k].mons.some(m => mon(S, m[0]).toLowerCase().includes(t))));
      cnt.textContent = rows.length + " of " + W.length + " areas";
      out.replaceChildren(...rows.map(w => el("section", { class: "battle", id: w.map }, el("h3", { style: "margin:0" }, w.name), el("div", { class: "sub" }, "map " + w.map),
        el("div", { class: "two" }, ["land", "water", "rock", "fish"].map(k => block(w, k))))));
      if (location.hash) { const e = document.getElementById(location.hash.slice(1)); if (e && e.scrollIntoView) e.scrollIntoView(); }
    }
    q.oninput = draw; draw();
  }

  /* ---------- Trainers ---------- */
  function party(t, S, M, I) {
    return el("div", { class: "party" }, t.party.map(p => el("div", { class: "m" }, el("b", {}, mon(S, p.sp)), " Lv " + p.lv,
      el("small", {}, p.mv.map(m => (M[m] || {}).name || "?").join(" · ") || "default moves"), p.item ? el("small", {}, "Holds " + ((I[p.item] || {}).name || "item " + p.item)) : null)));
  }
  function card(t, cls, S, M, I) {
    return el("div", { class: "battle" }, el("h4", {}, (cls[t.class] || "Trainer") + " " + t.name), el("div", { class: "sub" }, "trainer " + t.id + (t.double ? " · double battle" : "") + (t.items.length ? " · items: " + t.items.map(i => (I[i] || {}).name).join(", ") : "") + (t.where.length ? " · " + t.where.join(", ") : "")), party(t, S, M, I));
  }
  async function trainers() {
    const [X, D, M, I] = await Promise.all([load("misc"), load("species"), load("moves"), load("items")]);
    TYPES = D.types; const S = D.species, cls = X.classes, T = Object.values(X.trainers);
    const q = el("input", { type: "search", placeholder: "Trainer name or Pokémon", "aria-label": "Search trainers" });
    const cf = el("select", { "aria-label": "Trainer class" }, el("option", { value: "" }, "All classes"), [...new Set(T.map(t => t.class))].sort((a, b) => (cls[a] || "").localeCompare(cls[b] || "")).map(c => el("option", { value: c }, (cls[c] || "Class " + c) + " (" + T.filter(t => t.class === c).length + ")")));
    const cnt = el("span", { class: "count" }), out = el("div");
    $("#view").append(el("div", { class: "tools" }, q, cf, cnt), out);
    function draw() {
      const t = q.value.trim().toLowerCase();
      let rows = T.filter(x => (!cf.value || x.class === +cf.value) && (!t || x.name.toLowerCase().includes(t) || x.party.some(p => mon(S, p.sp).toLowerCase().includes(t)))).sort((a, b) => a.id - b.id);
      cnt.textContent = rows.length + " of " + T.length;
      out.replaceChildren(...rows.slice(0, 80).map(x => card(x, cls, S, M, I)));
      if (rows.length > 80) out.append(el("p", {}, "Showing 80. Filter by class or search to see the rest."));
    }
    q.oninput = cf.onchange = draw;
    if (location.hash) { const m = /class=(\d+)/.exec(location.hash); if (m) cf.value = m[1]; }
    draw();
  }

  /* ---------- battle widgets inside prose pages: <div class="bw" data-t="66,72"></div> ---------- */
  async function widgets() {
    const nodes = document.querySelectorAll(".bw[data-t]");
    if (!nodes.length) return;
    const [X, D, M, I] = await Promise.all([load("misc"), load("species"), load("moves"), load("items")]);
    nodes.forEach(n => {
      n.replaceChildren(...n.dataset.t.split(",").map(id => X.trainers[id] ? card(X.trainers[id], X.classes, D.species, M, I) : null));
    });
  }

  /* Spectrum Frontier brains and BP shop: <div class="fr" data-brain="Lance"> or <div class="fr" data-shop> */
  async function frontier() {
    const nodes = document.querySelectorAll(".fr");
    if (!nodes.length) return;
    const F = await load("frontier");
    nodes.forEach(n => {
      if (n.dataset.shop !== undefined) {
        n.append(el("div", { class: "tw" }, el("table", {}, el("thead", {}, el("tr", {}, el("th", {}, "Item"), el("th", { class: "num" }, "Price (BP)"), el("th", { class: "num" }, "Qty"))),
          el("tbody", {}, F.shop.map(i => el("tr", {}, el("td", {}, i.item), el("td", { class: "num" }, i.price), el("td", { class: "num" }, i.qty || 1)))))));
        return;
      }
      const b = F.brains[n.dataset.brain];
      if (!b) return;
      n.append(el("div", { class: "battle" }, el("h4", {}, n.dataset.brain + ", " + b.title), el("div", { class: "sub" }, "Lv 50 · three or four of these six are used per battle"),
        el("div", { class: "party" }, b.sets.map(s => el("div", { class: "m" }, el("b", {}, s.species), el("small", {}, s.moves.join(" · ")), el("small", {}, "Holds " + s.item))))));
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    chrome();
    const v = document.body.dataset.view;
    const run = { pokedex, moves, items, locations, trainers }[v];
    const root = $("#view");
    if (root) root.append(el("p", { class: "loading" }, "Loading data..."));
    const done = () => { const l = $(".loading"); if (l) l.remove(); };
    const fail = e => { done(); (root || document.body).append(el("div", { class: "box warn" }, el("b", { class: "lab" }, "Could not load data"), el("p", {}, "Open this guide from a web server (GitHub Pages, or run python3 -m http.server in docs/guide). Details: " + e.message))); };
    (run ? run() : Promise.resolve()).then(done).catch(fail);
    widgets().catch(fail);
    frontier().catch(fail);
  });
})();
