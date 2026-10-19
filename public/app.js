/* Mi Plataforma — PWA sin dependencias (hls.js se carga solo si hace falta).
   Regla de oro: la app NUNCA dice que algo funciona si no hay un estado "ok" generado por el verificador. */
"use strict";

const HLS_CDN = "https://cdnjs.cloudflare.com/ajax/libs/hls.js/1.5.20/hls.min.js";
const TMDB_TTL_DAYS = 30; // conservador: no confirmé el límite oficial de caché de TMDB
const PAGE = 120;

const STATUS_TEXT = {
  ok: "Funciona",
  restricted: "Acceso restringido",
  dead: "Caído",
  bad_format: "Formato no compatible",
  unchecked: "Sin verificar",
  fixture: "Dato de prueba",
  external: "Sitio externo",
};
const STATUS_HELP = {
  restricted: "Respondió 401/403/451 al verificador: puede ser geobloqueo o exigir cabeceras. Probalo en tu celular.",
  dead: "El verificador no pudo abrir este enlace.",
  bad_format: "El enlace responde, pero no es un video o lista HLS válida.",
  unchecked: "Todavía no pasó por el verificador.",
  fixture: "Es un ejemplo para probar la interfaz. No hay video real detrás.",
  external: "Se abre en el sitio oficial, fuera de esta app. Puede pedir registro gratuito.",
};
const RANK = { ok: 0, external: 1, unchecked: 2, restricted: 3, bad_format: 4, dead: 5, fixture: 6 };
const CATEGORY_ES = {
  general: "General", news: "Noticias", sports: "Deportes", kids: "Infantil", music: "Música", movies: "Películas",
  series: "Series", entertainment: "Entretenimiento", culture: "Cultura", education: "Educación",
  documentary: "Documentales", religious: "Religión", business: "Economía", weather: "Clima", comedy: "Comedia",
  lifestyle: "Estilo de vida", science: "Ciencia", legislative: "Legislativo", public: "Público", family: "Familia",
  animation: "Animación", classic: "Clásicos", cooking: "Cocina", travel: "Viajes", outdoor: "Aire libre",
  relax: "Relax", shop: "Compras", auto: "Autos", interactive: "Interactivo",
};
const LANG_ES = { es: "Español", en: "Inglés", spa: "Español", eng: "Inglés", por: "Portugués", fra: "Francés" };

const $ = (sel) => document.querySelector(sel);
function el(tag, props = {}, ...kids) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (k === "class") node.className = v;
    else if (k === "text") node.textContent = v;
    else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
    else if (v !== null && v !== undefined && v !== false) node.setAttribute(k, v === true ? "" : v);
  }
  for (const kid of kids.flat()) if (kid) node.append(kid);
  return node;
}

const state = {
  tab: "live",
  data: { live: null, movies: null, series: null },
  f: {
    live: { q: "", country: "AR", category: "", lang: "", onlyOk: false },
    movies: { q: "", genre: "", decade: "", lang: "", sort: "popularity", onlyOk: false },
    series: { q: "", genre: "" },
  },
  shown: PAGE,
  hls: null,
  current: null,
  report: null,
};

/* ---------- Estado de las fuentes ---------- */
function bestSource(item) {
  const srcs = item.sources || [];
  return srcs.slice().sort((a, b) => (RANK[a.status] ?? 9) - (RANK[b.status] ?? 9))[0] || null;
}
function itemStatus(item) {
  if (item.kind === "series") {
    const all = (item.seasons || []).flatMap((s) => s.episodes.flatMap((e) => e.sources || []));
    return all.length ? all.sort((a, b) => (RANK[a.status] ?? 9) - (RANK[b.status] ?? 9))[0].status : "unchecked";
  }
  const s = bestSource(item);
  return s ? s.status : "unchecked";
}
function fmtDate(iso) {
  if (!iso) return "";
  try { return new Date(iso).toLocaleDateString("es-AR", { day: "numeric", month: "short" }); } catch { return ""; }
}
function badge(src) {
  const status = src.status || "unchecked";
  const text = STATUS_TEXT[status] || status;
  const when = status === "ok" && src.checked ? ` · ${fmtDate(src.checked)}` : "";
  return el("span", { class: `badge ${status}`, text: text + when });
}
function flagTexts(src) {
  const out = [];
  if ((src.flags || []).includes("http_sin_cifrar") || (src.url || "").startsWith("http://")) out.push("HTTP sin cifrar");
  if ((src.flags || []).includes("exige_cabeceras") || src.referrer || src.user_agent) out.push("Exige cabeceras propias");
  return out;
}
function browserPlayable(src) {
  if (!src || src.type === "external" || src.status === "fixture" || src.status === "dead") return false;
  if (!src.url.startsWith("https://")) return false;
  if (src.referrer || src.user_agent) return false;
  return true;
}

/* ---------- Carga de datos ---------- */
async function loadAll() {
  const names = ["live", "movies", "series"];
  try {
    const rr = await fetch("data/report.json", { cache: "no-cache" });
    state.report = rr.ok ? await rr.json() : null;
  } catch { state.report = null; }
  await Promise.all(names.map(async (n) => {
    try {
      const r = await fetch(`data/${n}.json`, { cache: "no-cache" });
      state.data[n] = r.ok ? await r.json() : { items: [] };
    } catch { state.data[n] = { items: [] }; }
  }));
  renderBanner();
  buildFilters();
  render();
}
function renderBanner() {
  const b = $("#banner");
  const all = ["live", "movies", "series"].map((n) => state.data[n]).filter(Boolean);
  const fixture = all.some((d) => (d.origin || "").startsWith("DATOS DE PRUEBA"));
  const unverified = all.some((d) => d.items.length && !d.verified_at);
  if (fixture) { b.hidden = false; b.textContent = "Estás viendo datos de prueba. Los canales y películas de esta lista son ejemplos sin video real."; }
  else if (unverified) { b.hidden = false; b.textContent = "Hay secciones que todavía no pasaron por el verificador: sus estados figuran como “Sin verificar”."; }
  else b.hidden = true;
}

/* ---------- Filtros ---------- */
function option(value, text) { return el("option", { value, text }); }
function field(label, control, full = false) {
  return el("div", { class: full ? "full" : "" }, label ? el("label", { text: label }) : null, control);
}
function select(id, opts, value, onchange) {
  const s = el("select", { id });
  opts.forEach(([v, t]) => s.append(option(v, t)));
  s.value = value;
  s.addEventListener("change", () => { onchange(s.value); state.shown = PAGE; render(); });
  return s;
}
function searchBox(value, onchange) {
  const i = el("input", { type: "search", placeholder: "Buscar por nombre", value });
  i.addEventListener("input", () => { onchange(i.value.trim().toLowerCase()); state.shown = PAGE; render(); });
  return i;
}
function onlyOkBox(value, onchange) {
  const c = el("input", { type: "checkbox" });
  c.checked = value;
  c.addEventListener("change", () => { onchange(c.checked); state.shown = PAGE; render(); });
  return el("label", { class: "check" }, c, el("span", { text: "Solo los que figuran como “Funciona”" }));
}
function uniq(items, getter) {
  return [...new Set(items.flatMap((i) => getter(i) || []))].filter(Boolean).sort();
}
function buildFilters() {
  const box = $("#filters");
  box.replaceChildren();
  const t = state.tab;
  const f = state.f[t];
  const items = (state.data[t] && state.data[t].items) || [];
  if (t === "live") {
    const countries = [...new Map(items.map((i) => [i.country, i.country_name])).entries()];
    box.append(
      field("Buscar", searchBox(f.q, (v) => (f.q = v)), true),
      field("País", select("f-country", [["", "Todos"], ...countries], f.country, (v) => (f.country = v))),
      field("Categoría", select("f-cat", [["", "Todas"], ...uniq(items, (i) => i.categories).map((c) => [c, CATEGORY_ES[c] || c])], f.category, (v) => (f.category = v))),
      field("Idioma", select("f-lang", [["", "Todos"], ...uniq(items, (i) => i.languages).map((c) => [c, LANG_ES[c] || c])], f.lang, (v) => (f.lang = v))),
      field("", onlyOkBox(f.onlyOk, (v) => (f.onlyOk = v))),
    );
  } else if (t === "movies") {
    const decades = uniq(items, (i) => (i.year ? [String(Math.floor(i.year / 10) * 10)] : [])).reverse();
    box.append(
      field("Buscar", searchBox(f.q, (v) => (f.q = v)), true),
      field("Género", select("f-genre", [["", "Todos"], ...uniq(items, (i) => i.genres).map((g) => [g, g])], f.genre, (v) => (f.genre = v))),
      field("Década", select("f-dec", [["", "Todas"], ...decades.map((d) => [d, `${d}s`])], f.decade, (v) => (f.decade = v))),
      field("Idioma", select("f-lang", [["", "Todos"], ...uniq(items, (i) => i.languages).map((c) => [c, LANG_ES[c] || c])], f.lang, (v) => (f.lang = v))),
      field("Ordenar por", select("f-sort", [["popularity", "Popularidad"], ["year", "Año (nuevas primero)"], ["title", "Título"]], f.sort, (v) => (f.sort = v))),
      field("", onlyOkBox(f.onlyOk, (v) => (f.onlyOk = v)), true),
    );
  } else {
    box.append(
      field("Buscar", searchBox(f.q, (v) => (f.q = v)), true),
      field("Género", select("f-genre", [["", "Todos"], ...uniq(items, (i) => i.genres).map((g) => [g, g])], f.genre, (v) => (f.genre = v)), true),
    );
  }
}

/* ---------- Listados ---------- */
function filtered() {
  const t = state.tab;
  const f = state.f[t];
  let items = ((state.data[t] && state.data[t].items) || []).slice();
  const text = (i) => (i.name || i.title || "").toLowerCase();
  if (f.q) items = items.filter((i) => text(i).includes(f.q));
  if (t === "live") {
    if (f.country) items = items.filter((i) => i.country === f.country);
    if (f.category) items = items.filter((i) => (i.categories || []).includes(f.category));
    if (f.lang) items = items.filter((i) => (i.languages || []).includes(f.lang));
    if (f.onlyOk) items = items.filter((i) => itemStatus(i) === "ok");
  } else if (t === "movies") {
    if (f.genre) items = items.filter((i) => (i.genres || []).includes(f.genre));
    if (f.decade) items = items.filter((i) => i.year && String(Math.floor(i.year / 10) * 10) === f.decade);
    if (f.lang) items = items.filter((i) => (i.languages || []).includes(f.lang));
    if (f.onlyOk) items = items.filter((i) => itemStatus(i) === "ok");
    const sorters = {
      popularity: (a, b) => (b.popularity || 0) - (a.popularity || 0),
      year: (a, b) => (b.year || 0) - (a.year || 0),
      title: (a, b) => a.title.localeCompare(b.title, "es"),
    };
    items.sort(sorters[f.sort]);
  } else if (f.genre) items = items.filter((i) => (i.genres || []).includes(f.genre));
  return items;
}
const SERIES_NOTE = "Límite conocido: no hay una fuente gratuita y autorizada de series que se pueda automatizar. " +
  "Acá solo aparecen enlaces a plataformas oficiales y las series que cargues vos en data/manual/series.json.";
function render() {
  const list = $("#list");
  const items = filtered();
  list.replaceChildren();
  $("#tab-note").textContent = SERIES_NOTE;
  $("#tab-note").hidden = state.tab !== "series";
  list.classList.toggle("grid", state.tab !== "live");
  if (!items.length) {
    const total = ((state.data[state.tab] && state.data[state.tab].items) || []).length;
    list.append(el("p", { class: "empty", text: total
      ? "Ningún resultado con estos filtros. Probá quitar alguno."
      : (state.tab === "series"
        ? "Todavía no hay series. No encontré una fuente gratuita y autorizada que se pueda automatizar; podés agregar las tuyas en data/manual/series.json."
        : "No hay datos para esta sección. Ejecutá la actualización desde GitHub (ver README).") }));
  }
  items.slice(0, state.shown).forEach((it) => list.append(state.tab === "live" ? liveRow(it) : posterCard(it)));
  $("#btn-more").hidden = items.length <= state.shown;
  if (state.tab === "movies") enrichVisible(items.slice(0, state.shown));
}
function liveRow(ch) {
  const src = bestSource(ch);
  const status = src ? src.status : "unchecked";
  const bits = [ch.country_name, (CATEGORY_ES[(ch.categories || [])[0]] || (ch.categories || [])[0] || ""), src && src.quality].filter(Boolean).join(" · ");
  return el("button", { class: "row-item", "data-s": status, onclick: () => openPlayer(ch, src) },
    el("span", { class: "bar" }),
    el("span", { class: "main" },
      el("div", { class: "name", text: ch.name }),
      el("div", { class: "sub" }, src ? badge(src) : null, bits)),
    el("span", { class: "go", text: "Ver" }));
}
function posterCard(it) {
  const poster = it.poster || tmdbCached(it)?.poster;
  const box = el("div", { class: "poster" }, poster ? el("img", { src: poster, alt: "", loading: "lazy", referrerpolicy: "no-referrer",
    onerror: (e) => { e.target.replaceWith(el("span", { text: it.title })); } }) : el("span", { text: it.title }));
  const sub = [it.year, (it.genres || [])[0]].filter(Boolean).join(" · ");
  const st = itemStatus(it);
  return el("button", { class: "poster-card", "data-id": it.id, onclick: () => openDetail(it) }, box,
    el("div", { class: "t", text: it.title }),
    el("div", { class: "s" }, el("span", { class: `badge ${st}`, text: STATUS_TEXT[st] }), sub));
}

/* ---------- Reproductor ---------- */
function openPlayer(item, src) {
  const dlg = $("#player");
  const video = $("#video");
  stopPlayback();
  state.current = { item, src };
  $("#player-title").textContent = item.title || item.name;
  const msg = $("#player-msg");
  const actions = $("#player-actions");
  actions.replaceChildren();
  video.hidden = false;
  if (!src) { msg.textContent = "Este elemento no tiene fuentes de reproducción."; video.hidden = true; dlg.showModal(); return; }

  const flags = flagTexts(src);
  const notes = [STATUS_HELP[src.status], src.reason && src.status !== "fixture" ? src.reason : "", flags.length ? `Aviso: ${flags.join(", ")}.` : ""].filter(Boolean);
  msg.textContent = notes.join(" ");

  if (src.type === "external") {
    video.hidden = true;
    actions.append(el("a", { class: "primary", href: src.url, target: "_blank", rel: "noopener", text: "Abrir en el sitio oficial" }));
  } else if (src.status === "fixture") {
    video.hidden = true;
  } else {
    actions.append(vlcButton(src.url), copyButton(src.url));
    if (browserPlayable(src)) tryBrowser(video, src, msg);
    else {
      video.hidden = true;
      msg.textContent += " Se abre mejor con un reproductor externo (VLC).";
    }
  }
  if (item.origin_url) actions.append(el("a", { href: item.origin_url, target: "_blank", rel: "noopener", text: "Ver origen y licencia" }));
  dlg.showModal();
}
function vlcButton(url) {
  const m = url.match(/^(https?):\/\/(.*)$/);
  const href = m ? `intent://${m[2]}#Intent;scheme=${m[1]};package=org.videolan.vlc;type=video/*;end` : url;
  return el("a", { class: "primary", href, text: "Abrir en VLC" });
}
function copyButton(url) {
  return el("button", { text: "Copiar enlace", onclick: async (e) => {
    try { await navigator.clipboard.writeText(url); e.target.textContent = "Enlace copiado"; }
    catch { window.prompt("Copiá el enlace:", url); }
  } });
}
function loadHls() {
  return new Promise((resolve, reject) => {
    if (window.Hls) return resolve(window.Hls);
    const s = el("script", { src: HLS_CDN });
    s.onload = () => resolve(window.Hls);
    s.onerror = () => reject(new Error("No se pudo cargar hls.js"));
    document.head.append(s);
  });
}
async function tryBrowser(video, src, msg) {
  const fail = (why) => { video.hidden = true; msg.textContent += ` No se pudo reproducir en el navegador (${why}). Usá VLC.`; };
  try {
    if (src.type === "hls" || src.url.includes(".m3u8")) {
      const Hls = await loadHls();
      if (Hls && Hls.isSupported()) {
        state.hls = new Hls();
        state.hls.on(Hls.Events.ERROR, (_, d) => { if (d.fatal) fail(d.details || "error HLS; suele ser falta de CORS"); });
        state.hls.loadSource(src.url);
        state.hls.attachMedia(video);
      } else if (video.canPlayType("application/vnd.apple.mpegurl")) video.src = src.url;
      else return fail("HLS no soportado");
    } else video.src = src.url;
    video.onerror = () => fail("el navegador rechazó el archivo");
    await video.play().catch(() => {});
  } catch (e) { fail(e.message); }
}
function stopPlayback() {
  const video = $("#video");
  if (state.hls) { state.hls.destroy(); state.hls = null; }
  video.pause();
  video.removeAttribute("src");
  video.load();
}

/* ---------- Detalle (películas y series) ---------- */
async function openDetail(it) {
  const dlg = $("#detail");
  $("#detail-title").textContent = it.title;
  const body = $("#detail-body");
  body.replaceChildren();
  const cached = tmdbCached(it);
  const overview = it.overview || (cached && cached.overview) || "Sin sinopsis disponible.";
  const facts = [it.year, (it.genres || []).join(", "), (it.languages || []).map((l) => LANG_ES[l] || l).join(", ")].filter(Boolean).join(" · ");
  body.append(el("p", { class: "facts", text: facts }), el("p", { text: overview }));
  if (it.license || it.origin) {
    body.append(el("div", { class: "rights" },
      `Origen: ${it.origin || "—"}. Licencia: ${it.license || "no declarada"}. ` + (it.rights_note || "")));
  }
  if (it.kind === "series") {
    (it.seasons || []).forEach((s) => {
      const sec = el("div", { class: "season" }, el("h3", { text: `Temporada ${s.number}` }));
      s.episodes.forEach((ep) => {
        const src = bestSource(ep);
        sec.append(el("div", { class: "ep" },
          el("span", {}, `${ep.number}. ${ep.title || "Episodio"} `, src ? badge(src) : null),
          el("button", { class: "btn", text: "Ver", onclick: () => { dlg.close(); openPlayer({ title: `${it.title} · T${s.number}E${ep.number}`, origin_url: it.origin_url }, src); } })));
      });
      body.append(sec);
    });
  } else {
    const src = bestSource(it);
    if (src) body.append(el("div", { class: "player-actions" },
      badge(src),
      el("button", { class: "btn", text: "Ver", onclick: () => { dlg.close(); openPlayer(it, src); } })));
  }
  dlg.showModal();
}

/* ---------- TMDB opcional (clave del propio usuario, solo en este teléfono) ---------- */
function tmdbKey() { try { return localStorage.getItem("tmdb_key") || ""; } catch { return ""; } }
function tmdbCached(it) {
  try {
    const raw = localStorage.getItem(`tmdb:${it.id}`);
    if (!raw) return null;
    const v = JSON.parse(raw);
    if (Date.now() - v.t > TMDB_TTL_DAYS * 864e5) { localStorage.removeItem(`tmdb:${it.id}`); return null; }
    return v;
  } catch { return null; }
}
async function enrichVisible(items) {
  const key = tmdbKey();
  if (!key) return;
  let budget = 12;
  for (const it of items) {
    if (budget <= 0) break;
    if (it.poster || tmdbCached(it) || it.origin === "Fixture") continue;
    budget--;
    try {
      const url = `https://api.themoviedb.org/3/search/movie?api_key=${encodeURIComponent(key)}&language=es-MX&query=${encodeURIComponent(it.title)}${it.year ? `&year=${it.year}` : ""}`;
      const r = await fetch(url);
      if (!r.ok) { if (r.status === 401) break; continue; }
      const hit = ((await r.json()).results || [])[0];
      const v = { t: Date.now(), poster: hit && hit.poster_path ? `https://image.tmdb.org/t/p/w342${hit.poster_path}` : null, overview: hit ? hit.overview : "" };
      localStorage.setItem(`tmdb:${it.id}`, JSON.stringify(v));
      const card = document.querySelector(`.poster-card[data-id="${CSS.escape(it.id)}"] .poster`);
      if (card && v.poster) card.replaceChildren(el("img", { src: v.poster, alt: "", loading: "lazy" }));
    } catch { break; }
  }
}
function clearTmdb() {
  try {
    Object.keys(localStorage).filter((k) => k === "tmdb_key" || k.startsWith("tmdb:")).forEach((k) => localStorage.removeItem(k));
  } catch { /* sin almacenamiento */ }
}

/* ---------- Eventos ---------- */
document.querySelectorAll(".tabs button").forEach((b) => b.addEventListener("click", () => {
  document.querySelectorAll(".tabs button").forEach((x) => x.setAttribute("aria-selected", String(x === b)));
  state.tab = b.dataset.tab;
  state.shown = PAGE;
  buildFilters();
  render();
  window.scrollTo({ top: 0 });
}));
$("#btn-more").addEventListener("click", () => { state.shown += PAGE; render(); });
$("#player-close").addEventListener("click", () => $("#player").close());
$("#player").addEventListener("close", stopPlayback);
$("#detail-close").addEventListener("click", () => $("#detail").close());
$("#btn-settings").addEventListener("click", () => {
  $("#tmdb-key").value = tmdbKey();
  const parts = ["live", "movies", "series"].map((n) => {
    const d = state.data[n];
    return d ? `${n}: ${d.items.length} elementos, generado ${fmtDate(d.generated) || "—"}, verificado ${fmtDate(d.verified_at) || "nunca"}` : `${n}: sin datos`;
  });
  const r = state.report;
  let health = "Todavía no hay informe de la última actualización.";
  if (r) {
    const bits = [`Última actualización: ${fmtDate(r.generated)}`];
    if (r.live_ok) bits.push(`canales que funcionaban: Argentina ${r.live_ok.argentina}, Latinoamérica ${r.live_ok.latam}`);
    if ((r.warnings || []).length) bits.push(`Advertencias: ${r.warnings.join(" ")}`);
    health = bits.join(". ") + ".";
  }
  $("#about-data").textContent = `${health} ${parts.join(" | ")}`;
  $("#settings").showModal();
});
$("#settings-close").addEventListener("click", () => $("#settings").close());
$("#tmdb-save").addEventListener("click", () => {
  try { localStorage.setItem("tmdb_key", $("#tmdb-key").value.trim()); } catch { /* sin almacenamiento */ }
  $("#settings").close();
  render();
});
$("#tmdb-clear").addEventListener("click", () => { clearTmdb(); $("#tmdb-key").value = ""; render(); });

if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js").catch(() => {});
loadAll();
