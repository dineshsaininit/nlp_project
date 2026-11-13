const PAGES = [
  ["overview", "Overview"],
  ["read", "Read one document"],
  ["compare", "Compare versions"],
  ["match", "Match resumes"],
  ["summary", "Summarise"],
  ["ask", "Ask a question"],
  ["graph", "Knowledge graph"],
  ["playground", "NLP playground"],
  ["quality", "Quality checks"],
  ["export", "Report and export"],
];

const PALETTE = ["#1f3a5f", "#a8361c", "#2e6a3e", "#9a6400", "#6b4e8a", "#4f6d7a", "#9c3d63", "#7a8c3a"];
const MOOD_COLOURS = { Positive: "#2e6a3e", Neutral: "#a39e92", Negative: "#a8361c" };

const state = {
  documents: [],
  roles: null,
  settings: null,
  history: [],
  read: { name: null, tab: "Summary" },
  compare: null,
  match: null,
  summary: null,
  graph: null,
  playgroundTab: "Pipeline",
};

const main = document.getElementById("main");
let ticket = 0;
let busyCount = 0;

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function num(value, digits) {
  if (typeof value !== "number") return esc(value ?? "");
  if (Number.isInteger(value) && digits === undefined) return value.toLocaleString("en-US");
  return value.toFixed(digits ?? 2);
}

function percent(value) {
  return `${Math.round((value || 0) * 100)}%`;
}

function short(text, size = 40) {
  text = String(text ?? "");
  return text.length <= size ? text : text.slice(0, size - 3) + "...";
}

function busy(on) {
  const bar = document.getElementById("busy");
  busyCount += on ? 1 : -1;
  if (busyCount > 0) {
    bar.className = "busy on";
  } else {
    busyCount = 0;
    bar.className = "busy done";
  }
}

function toast(message, bad = false) {
  const box = document.getElementById("toast");
  box.textContent = message;
  box.className = `toast show${bad ? " bad" : ""}`;
  clearTimeout(box.timer);
  box.timer = setTimeout(() => (box.className = "toast"), 4200);
}

async function api(path, options = {}) {
  busy(true);
  try {
    const response = await fetch(path, options);
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || `The server said ${response.status}`);
    return data;
  } finally {
    busy(false);
  }
}

const get = (path) => api(path);
const post = (path, payload) => api(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });

function tag(text, kind = "") {
  return `<span class="tag ${kind}">${esc(text)}</span>`;
}

function tags(items, kind = "", emptyText = "none") {
  items = items || [];
  return items.length ? items.map((item) => tag(item, kind)).join("") : `<span class="empty">${esc(emptyText)}</span>`;
}

function head(number, title, lede, tools = "") {
  return `<header class="page-head"><div class="kicker">${number} / ${esc(PAGES[Number(number) - 1][1])}</div>
    <h1>${esc(title)}</h1><p>${lede}</p>${tools ? `<div class="tools">${tools}</div>` : ""}</header>`;
}

function section(title, small = "") {
  return `<h2 class="section">${esc(title)}${small ? `<small>${esc(small)}</small>` : ""}</h2>`;
}

function figures(items) {
  return `<div class="figures">${items
    .map(([value, label, sub, word]) => `<div class="figure"><div class="n${word ? " word" : ""}">${esc(value)}</div><div class="l">${esc(label)}</div>${sub ? `<div class="s">${esc(sub)}</div>` : ""}</div>`)
    .join("")}</div>`;
}

function box(title, inner) {
  return `<div class="box"><h3>${esc(title)}</h3>${inner}</div>`;
}

function chartBox(id, title, note = "") {
  return `<div class="chart"><div class="chart-title">${esc(title)}</div>${note ? `<div class="chart-note">${esc(note)}</div>` : ""}<div id="${id}"></div></div>`;
}

function loading(text = "Working on it") {
  return `<p class="loading">${esc(text)}...</p>`;
}

function errorBox(message) {
  return `<div class="error">${esc(message)}</div>`;
}

function guessColumns(rows) {
  return Object.keys(rows[0]).map((key) => ({ key, kind: typeof rows[0][key] === "number" ? "num" : "text" }));
}

function table(rows, columns) {
  if (!rows || !rows.length) return `<p class="empty">Nothing to show.</p>`;
  columns = columns || guessColumns(rows);
  const header = columns.map((c) => `<th>${esc(c.label || c.key)}</th>`).join("");
  const body = rows
    .map((row) => `<tr>${columns.map((c) => cell(row[c.key], c, row)).join("")}</tr>`)
    .join("");
  return `<div class="table-wrap"><table class="data"><thead><tr>${header}</tr></thead><tbody>${body}</tbody></table></div>`;
}

function cell(value, column, row) {
  if (column.render) return `<td>${column.render(value, row)}</td>`;
  if (column.kind === "meter") {
    const width = Math.max(0, Math.min(100, ((value || 0) / (column.max || 1)) * 100));
    return `<td class="num"><span class="meter"><i style="width:${width}%"></i></span>${num(value, column.digits)}</td>`;
  }
  if (column.kind === "num") return `<td class="num">${num(value, column.digits)}</td>`;
  if (typeof value === "boolean") return `<td>${value ? "yes" : "no"}</td>`;
  return `<td>${esc(value)}</td>`;
}

function plot(id, traces, layout = {}, height = 360) {
  const target = document.getElementById(id);
  if (!target || !window.Plotly) return;
  const axis = { gridcolor: "#e8e2d5", zerolinecolor: "#d6cfbf", linecolor: "#d6cfbf", automargin: true };
  const base = {
    height,
    margin: { l: 50, r: 24, t: 16, b: 46 },
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    font: { family: "Segoe UI, system-ui, sans-serif", size: 12, color: "#1d1c19" },
    colorway: PALETTE,
    legend: { orientation: "h", y: -0.18, font: { size: 11 } },
    hoverlabel: { bgcolor: "#1d1c19", bordercolor: "#1d1c19", font: { color: "#f4f1e9" } },
  };
  const merged = { ...base, ...layout, xaxis: { ...axis, ...(layout.xaxis || {}) }, yaxis: { ...axis, ...(layout.yaxis || {}) } };
  Plotly.newPlot(target, traces, merged, { displayModeBar: false, responsive: true });
}

function regexSafe(text) {
  return text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function highlight(text, terms) {
  const lookup = {};
  Object.entries(terms || {}).forEach(([term, kind]) => {
    if (term && term.trim()) lookup[term.toLowerCase()] = kind;
  });
  const keys = Object.keys(lookup).sort((a, b) => b.length - a.length);
  if (!keys.length) return esc(text);
  const pattern = new RegExp(`(?<![\\w])(${keys.map(regexSafe).join("|")})(?![\\w])`, "gi");
  let out = "";
  let last = 0;
  for (const found of String(text).matchAll(pattern)) {
    out += esc(text.slice(last, found.index));
    out += `<mark class="${lookup[found[0].toLowerCase()] || ""}">${esc(found[0])}</mark>`;
    last = found.index + found[0].length;
  }
  return out + esc(text.slice(last));
}

function checks(name, options, chosen) {
  return `<div class="checks">${options
    .map((option) => `<label><input type="checkbox" name="${name}" value="${esc(option)}"${chosen.includes(option) ? " checked" : ""}>${esc(option)}</label>`)
    .join("")}</div>`;
}

function checked(name) {
  return [...document.querySelectorAll(`input[name="${name}"]:checked`)].map((input) => input.value);
}

function select(id, options, chosen, extra = "") {
  return `<select id="${id}" class="input" ${extra}>${options
    .map((option) => {
      const [value, label] = Array.isArray(option) ? option : [option, option];
      return `<option value="${esc(value)}"${value === chosen ? " selected" : ""}>${esc(label)}</option>`;
    })
    .join("")}</select>`;
}

function tabsBar(names, current) {
  return `<div class="tabs" role="tablist">${names
    .map((name) => `<button type="button" data-tab="${esc(name)}" class="${name === current ? "on" : ""}">${esc(name)}</button>`)
    .join("")}</div>`;
}

function bindTabs(container, onPick) {
  container.querySelectorAll(".tabs button").forEach((button) => {
    button.addEventListener("click", () => {
      container.querySelectorAll(".tabs button").forEach((other) => other.classList.toggle("on", other === button));
      onPick(button.dataset.tab);
    });
  });
}

function names() {
  return state.documents.map((doc) => doc.name);
}

function downloadText(text, fileName) {
  const link = document.createElement("a");
  link.href = URL.createObjectURL(new Blob([text], { type: "text/plain" }));
  link.download = fileName;
  link.click();
  setTimeout(() => URL.revokeObjectURL(link.href), 2000);
}

function welcome() {
  main.innerHTML = `<header class="page-head"><div class="kicker">Start here</div><h1>Add the documents you want to study</h1>
    <p>Nothing is loaded yet. Drop files into the box on the left, or paste some text. Everything stays on this computer and runs with plain NLP, no AI service and no keys.</p></header>
    <ol class="steps">
      <li><div><b>Add documents</b><span>PDF, Word, TXT, Markdown, CSV and HTML files all work. Scanned PDFs without a text layer will be skipped.</span></div></li>
      <li><div><b>Pick a page on the left</b><span>Each page does one job: compare versions, rank resumes, summarise, answer questions and so on.</span></div></li>
      <li><div><b>Take the results with you</b><span>The last page builds a PDF report and exports CSV and JSON.</span></div></li>
    </ol>
    ${section("What each page needs")}
    ${table([
      { page: "Overview, Read, Summarise, Ask, Knowledge graph", upload: "Any documents", tip: "one file is enough" },
      { page: "Compare versions", upload: "Two versions of one document", tip: "policy_v1.pdf and policy_v2.pdf" },
      { page: "Match resumes", upload: "A job description and some resumes", tip: "job_backend.docx, resume_anna.pdf, cv_rahul.pdf" },
      { page: "Summary quality", upload: "A summary written by a person", tip: "reference_summary.txt" },
      { page: "NLP playground", upload: "Nothing", tip: "type your own text" },
    ], [{ key: "page", label: "Page" }, { key: "upload", label: "What to add" }, { key: "tip", label: "File name example" }])}
    ${box("A note on file names", `<p>The scanner reads file names to guess roles. <b>job</b> means a job description, <b>resume</b> or <b>cv</b> means a resume, <b>reference</b> means a reference summary, and the same name with different numbers (<b>_v1</b>, <b>_v2</b>, <b>2024</b>, <b>2025</b>) means versions of one document. You can still pick any files by hand on each page.</p>`)}`;
}

async function overviewPage(myTicket) {
  const top = head("01", "Overview", "A first look at everything you added: how big each file is, what kind of document it seems to be, how the files relate to each other and which topics run through them.");
  main.innerHTML = top + loading("Reading the documents");
  const data = await get("/api/overview");
  if (myTicket !== ticket) return;
  const roles = data.roles;
  const totals = data.totals;
  const versionText = roles.version_groups.length ? roles.version_groups.map((group) => tag(group.join("  >  "), "warn")).join("") : `<span class="empty">none found</span>`;
  main.innerHTML = top +
    figures([
      [num(totals.documents), "documents"],
      [num(totals.words), "words"],
      [num(totals.sentences), "sentences"],
      [num(totals.vocabulary), "distinct terms"],
      [num(totals.topics), "topics"],
      [num(totals.versions), "version groups"],
    ]) +
    section("What the scanner worked out", "from file names and content") +
    `<div class="cols">
      ${box("Roles", `<p><b>Job description</b><br>${tags(roles.job_file ? [roles.job_file] : [], "mark", "none found")}</p>
        <p><b>Resumes</b><br>${tags(roles.resume_files, "mark", "none found")}</p>
        <p><b>Reference summary</b><br>${tags(roles.reference_file ? [roles.reference_file] : [], "mark", "none found")}</p>`)}
      ${box("Groups", `<p><b>Versions of the same document</b><br>${versionText}</p>
        <p><b>Topic groups used for summaries</b><br>${roles.summary_groups.map((group) => tag(group.join(", "))).join("")}</p>`)}
    </div>` +
    section("The documents") +
    table(data.table, [
      { key: "document", label: "Document" },
      { key: "type", label: "Looks like" },
      { key: "language", label: "Language" },
      { key: "words", label: "Words", kind: "num" },
      { key: "sentences", label: "Sentences", kind: "num" },
      { key: "readability", label: "Reading ease", kind: "meter", max: 100, digits: 0 },
      { key: "level", label: "Level" },
      { key: "mood", label: "Mood" },
      { key: "top keywords", label: "Keywords" },
    ]) +
    `<div class="cols">${chartBox("ov-heat", "How alike the documents are", "Cosine similarity of the document vectors. 1.00 means the same text.")}
      ${chartBox("ov-map", "Every sentence, placed by meaning", "Sentence vectors squeezed into two dimensions with PCA. Dots that sit close say similar things.")}</div>
     <div class="cols">${chartBox("ov-types", "What kind of documents these are", "A guess from vocabulary clues.")}
      ${chartBox("ov-length", "Length and mood", "Words per document, coloured by the average VADER score.")}</div>` +
    section("Topics running through the files", "found with NMF on TF-IDF") +
    `<div class="cols three">${data.topics
      .map((topic, index) => box(`Topic ${index + 1}`, `<p>${tags(topic.words, "mark")}</p><p class="note">Mostly in ${esc(topic.documents.join(", ") || "no single file")}</p>`))
      .join("")}</div>`;

  const labels = data.names.map((name) => short(name, 26));
  plot("ov-heat", [{
    type: "heatmap", z: data.similarity, x: labels, y: labels, zmin: 0, zmax: 1,
    colorscale: [[0, "#fffdf8"], [0.5, "#9fb0c6"], [1, "#1f3a5f"]], texttemplate: "%{z:.2f}", textfont: { size: 10 },
    hovertemplate: "%{y}<br>%{x}<br>%{z:.2f}<extra></extra>", showscale: false,
  }], { margin: { l: 10, r: 10, t: 10, b: 10 }, xaxis: { tickangle: 40 }, yaxis: { autorange: "reversed" } }, Math.max(380, 34 * labels.length + 160));

  const byDoc = {};
  (data.points || []).forEach((point) => {
    (byDoc[point.document] = byDoc[point.document] || { x: [], y: [], text: [] });
    byDoc[point.document].x.push(point.x);
    byDoc[point.document].y.push(point.y);
    byDoc[point.document].text.push(short(point.sentence, 90));
  });
  plot("ov-map", Object.entries(byDoc).map(([name, points]) => ({
    type: "scatter", mode: "markers", name: short(name, 22), x: points.x, y: points.y, text: points.text,
    marker: { size: 9, opacity: 0.8, line: { width: 1, color: "#fffdf8" } }, hovertemplate: "%{text}<extra>" + esc(short(name, 22)) + "</extra>",
  })), { xaxis: { showticklabels: false, zeroline: false }, yaxis: { showticklabels: false, zeroline: false } }, Math.max(380, 34 * labels.length + 160));

  const typeCounts = {};
  data.table.forEach((row) => (typeCounts[row.type] = (typeCounts[row.type] || 0) + 1));
  const typeNames = Object.keys(typeCounts).sort((a, b) => typeCounts[a] - typeCounts[b]);
  plot("ov-types", [{ type: "bar", orientation: "h", x: typeNames.map((name) => typeCounts[name]), y: typeNames, marker: { color: "#1f3a5f" }, hovertemplate: "%{y}: %{x}<extra></extra>" }],
    { margin: { l: 10, r: 20, t: 10, b: 40 }, xaxis: { dtick: 1 } }, 300);

  const sorted = [...data.table].sort((a, b) => a.words - b.words);
  plot("ov-length", [{
    type: "bar", orientation: "h", x: sorted.map((row) => row.words), y: sorted.map((row) => short(row.document, 24)),
    marker: { color: sorted.map((row) => MOOD_COLOURS[row.mood]) }, text: sorted.map((row) => row.mood), hovertemplate: "%{y}<br>%{x} words, %{text}<extra></extra>",
  }], { margin: { l: 10, r: 20, t: 10, b: 40 } }, Math.max(300, 26 * sorted.length + 60));
}

async function readPage(myTicket) {
  const all = names();
  if (!all.includes(state.read.name)) state.read.name = all[0];
  const tools = `<label class="field">Document${select("read-doc", all, state.read.name)}</label>`;
  const top = head("02", "Read one document", "Pick a file and look at it from several angles: what it is about, how it is written, how the mood moves, and which names, numbers and skills it mentions.", tools);
  main.innerHTML = top + loading("Analysing the document");
  bindReadPicker();
  const doc = await get(`/api/document?name=${encodeURIComponent(state.read.name)}`);
  if (myTicket !== ticket) return;
  const r = doc.readability;
  main.innerHTML = top +
    figures([
      [num(doc.words), "words", `${doc.sentences} sentences`],
      [num(r["Flesch reading ease"], 1), "reading ease", readingLevel(r["Flesch reading ease"])],
      [num(r["Flesch-Kincaid grade"], 1), "school grade", "Flesch-Kincaid"],
      [doc.mood.label, "mood", `VADER ${num(doc.mood.score, 2)}`, true],
      [doc.language.label, "language", `confidence ${num(doc.language.confidence, 2)}`, true],
      [doc.type.label, "looks like", `confidence ${num(doc.type.confidence, 2)}`, true],
    ]) +
    tabsBar(["Summary", "Keywords", "Style", "Sentiment", "Names and skills", "Full text"], state.read.tab) +
    `<div id="read-tab"></div>`;
  bindReadPicker();
  bindTabs(main, (name) => {
    state.read.tab = name;
    showReadTab(doc, name);
  });
  showReadTab(doc, state.read.tab);
}

function bindReadPicker() {
  const picker = document.getElementById("read-doc");
  if (picker) picker.addEventListener("change", () => {
    state.read.name = picker.value;
    route();
  });
}

function readingLevel(score) {
  if (score >= 70) return "easy";
  if (score >= 50) return "medium";
  if (score >= 30) return "hard";
  return "very hard";
}

function showReadTab(doc, name) {
  const area = document.getElementById("read-tab");
  if (name === "Summary") {
    area.innerHTML = `<div class="box"><h3>In short</h3><p class="summary-text">${esc(doc.summary || "This document is too short to summarise.")}</p></div>
      <div class="cols">${box("Top keywords (TF-IDF)", tags(doc.keywords.slice(0, 12).map(([word]) => word), "mark"))}
      ${box("Key phrases (RAKE)", tags(doc.rake.slice(0, 12).map(([phrase]) => phrase)))}</div>
      ${chartBox("read-type", "Why it was filed under this type", "Share of words that match each type's clue list.")}`;
    const scores = [...doc.type.scores].reverse();
    plot("read-type", [{ type: "bar", orientation: "h", x: scores.map((s) => s[1]), y: scores.map((s) => s[0]), marker: { color: scores.map((s) => (s[0] === doc.type.label ? "#a8361c" : "#9fb0c6")) } }],
      { margin: { l: 10, r: 20, t: 10, b: 40 } }, 320);
  }
  if (name === "Keywords") {
    const top = doc.keywords;
    const highest = Math.max(...top.map((k) => k[1]), 0.0001);
    const cloud = top.map(([word, weight]) => `<span style="font-size:${(13 + (weight / highest) * 22).toFixed(0)}px;opacity:${(0.55 + (weight / highest) * 0.45).toFixed(2)}">${esc(word)}</span>`).join(" ");
    area.innerHTML = `<div class="box"><h3>Keywords sized by weight</h3><p class="cloud">${cloud || '<span class="empty">no keywords</span>'}</p></div>
      <div class="cols">${chartBox("read-weights", "Top TF-IDF weights")}<div>
        ${section("Key phrases", "RAKE scores")}${table(doc.rake.map(([phrase, score]) => ({ phrase, score })), [{ key: "phrase", label: "Phrase" }, { key: "score", label: "Score", kind: "num", digits: 1 }])}
        ${section("Word pairs that stick together", "log likelihood")}${table(doc.pairs.map(([pair, score, count]) => ({ pair, score, count })), [{ key: "pair", label: "Pair" }, { key: "score", label: "Score", kind: "num", digits: 1 }, { key: "count", label: "Seen", kind: "num" }])}
      </div></div>`;
    const firstTwelve = top.slice(0, 12).reverse();
    plot("read-weights", [{ type: "bar", orientation: "h", x: firstTwelve.map((k) => k[1]), y: firstTwelve.map((k) => k[0]), marker: { color: "#1f3a5f" } }], { margin: { l: 10, r: 20, t: 10, b: 40 } }, 420);
  }
  if (name === "Style") {
    const r = doc.readability;
    const s = doc.style;
    area.innerHTML = figures([
      [num(s["lexical diversity"], 2), "lexical diversity", "unique words / words"],
      [num(s["average word length"], 1), "letters per word"],
      [percent(s["long word ratio"]), "long words", "7 letters or more"],
      [num(r["Gunning fog"], 1), "Gunning fog", "years of school"],
      [num(r["SMOG index"], 1), "SMOG index"],
    ]) + `<div class="cols">${chartBox("read-pos", "Parts of speech", "Counted with the NLTK perceptron tagger.")}${chartBox("read-zipf", "Zipf's law", "Word rank against how often it appears, both on log scales.")}</div>
      ${chartBox("read-words", "Words used most often", "After stopwords are removed and words are lemmatized.")}`;
    const pos = Object.entries(s["pos counts"]).sort((a, b) => a[1] - b[1]);
    plot("read-pos", [{ type: "bar", orientation: "h", x: pos.map((p) => p[1]), y: pos.map((p) => p[0]), marker: { color: "#2e6a3e" } }], { margin: { l: 10, r: 20, t: 10, b: 40 } }, 320);
    plot("read-zipf", [{ type: "scatter", mode: "markers", x: doc.zipf.map((z) => z.rank), y: doc.zipf.map((z) => z.count), text: doc.zipf.map((z) => z.word), marker: { color: "#a8361c", size: 7, opacity: 0.7 }, hovertemplate: "%{text}: %{y}<extra></extra>" }],
      { xaxis: { type: "log", title: { text: "rank" } }, yaxis: { type: "log", title: { text: "count" } } }, 320);
    const words = doc.zipf.slice(0, 18);
    plot("read-words", [{ type: "bar", x: words.map((w) => w.word), y: words.map((w) => w.count), marker: { color: "#1f3a5f" } }], { xaxis: { tickangle: 35 } }, 320);
  }
  if (name === "Sentiment") {
    const arc = doc.arc;
    const best = [...arc].sort((a, b) => b.score - a.score).slice(0, 3);
    const worst = [...arc].sort((a, b) => a.score - b.score).slice(0, 3);
    const list = (rows) => `<ul class="links">${rows.map((row) => `<li>${esc(row.sentence)} <span class="note">(${num(row.score, 2)})</span></li>`).join("")}</ul>`;
    area.innerHTML = chartBox("read-arc", "How the mood moves through the text", "VADER compound score for every sentence, from -1 (negative) to +1 (positive).") +
      `<div class="cols">${box("Most positive sentences", list(best))}${box("Most negative sentences", list(worst))}</div>`;
    plot("read-arc", [{
      type: "scatter", mode: "lines+markers", x: arc.map((a) => a.position), y: arc.map((a) => a.score), text: arc.map((a) => short(a.sentence, 90)),
      line: { color: "#9fb0c6", width: 2 }, marker: { size: 9, color: arc.map((a) => (a.score > 0.05 ? "#2e6a3e" : a.score < -0.05 ? "#a8361c" : "#a39e92")) },
      hovertemplate: "Sentence %{x}<br>%{text}<br>%{y}<extra></extra>",
    }], { yaxis: { range: [-1.05, 1.05], title: { text: "score" } }, xaxis: { title: { text: "sentence" } }, shapes: [{ type: "line", xref: "paper", x0: 0, x1: 1, y0: 0, y1: 0, line: { color: "#8a8478", dash: "dot", width: 1 } }] }, 360);
  }
  if (name === "Names and skills") {
    const kinds = { PERSON: "", ORGANIZATION: "mark", PLACE: "ok", DATE: "warn", NUMBER: "warn", MONEY: "warn", EMAIL: "", URL: "" };
    const groups = Object.entries(doc.entities).map(([label, items]) => `<p><b>${esc(label.toLowerCase())}</b><br>${tags(items.map((i) => i[0]), kinds[label])}</p>`).join("");
    const terms = {};
    Object.entries(doc.entities).forEach(([label, items]) => items.forEach(([item]) => (terms[item] = label)));
    const skills = Object.entries(doc.skills).map(([skill, found]) => ({ skill, found }));
    area.innerHTML = `<div class="cols">${box("Names, places, dates and numbers", groups || `<p class="empty">Nothing found.</p>`)}
      <div>${box("Skills", tags(skills.map((s) => s.skill), "ok"))}${table(skills, [{ key: "skill", label: "Skill" }, { key: "found", label: "Found as" }])}</div></div>
      ${box("The text with entities marked", `<div class="reading">${highlight(doc.text, terms)}</div>`)}`;
  }
  if (name === "Full text") {
    const terms = {};
    doc.keywords.slice(0, 12).forEach(([word]) => (terms[word] = "kw"));
    area.innerHTML = `<p class="row"><button id="read-download" class="btn quiet small">Download the extracted text</button><span class="note">The top keywords are underlined.</span></p>
      <div class="box"><div class="reading">${highlight(doc.text, terms)}</div></div>`;
    document.getElementById("read-download").addEventListener("click", () => downloadText(doc.text, doc.name.replace(/\.[^.]+$/, "") + ".txt"));
  }
}

function defaultPair() {
  const groups = state.roles?.version_groups || [];
  const all = names();
  if (groups.length) return [groups[0][0], groups[0][1]];
  return [all[0], all[all.length - 1]];
}

async function comparePage(myTicket) {
  const all = names();
  if (!state.compare || !all.includes(state.compare.old) || !all.includes(state.compare.new)) {
    const [first, second] = defaultPair();
    state.compare = { mode: "files", old: first, new: second, oldText: "Every employee gets 12 days of leave.\nRequests go to the manager one week before.",
      newText: "Every employee gets 15 days of leave.\nRequests go to the manager one week before.\nStaff may work from home twice a month.", tab: "Changes", showSame: true };
  }
  const c = state.compare;
  const inputs = c.mode === "files"
    ? `<label class="field">Older version${select("cmp-old", all, c.old)}</label><label class="field">Newer version${select("cmp-new", all, c.new)}</label>`
    : `<label class="field">First text<textarea id="cmp-old-text" class="input" rows="4">${esc(c.oldText)}</textarea></label><label class="field">Second text<textarea id="cmp-new-text" class="input" rows="4">${esc(c.newText)}</textarea></label>`;
  const tools = `<div class="switch"><button type="button" data-mode="files" class="${c.mode === "files" ? "on" : ""}">Two files</button><button type="button" data-mode="text" class="${c.mode === "text" ? "on" : ""}">Two pasted texts</button></div>
    ${inputs}<button id="cmp-run" class="btn">Compare</button>`;
  main.innerHTML = head("03", "Compare versions", "Sentences become vectors and are lined up with the Needleman-Wunsch algorithm. Rewording counts as the same, while new facts, numbers and sentences are flagged.", tools) + `<div id="cmp-out">${loading("Aligning the sentences")}</div>`;
  main.querySelectorAll(".switch button").forEach((button) => button.addEventListener("click", () => {
    readCompareInputs();
    c.mode = button.dataset.mode;
    route();
  }));
  document.getElementById("cmp-run").addEventListener("click", () => {
    readCompareInputs();
    runCompare(ticket);
  });
  runCompare(myTicket);
}

function readCompareInputs() {
  const c = state.compare;
  if (document.getElementById("cmp-old")) {
    c.old = document.getElementById("cmp-old").value;
    c.new = document.getElementById("cmp-new").value;
  }
  if (document.getElementById("cmp-old-text")) {
    c.oldText = document.getElementById("cmp-old-text").value;
    c.newText = document.getElementById("cmp-new-text").value;
  }
}

async function runCompare(myTicket) {
  const c = state.compare;
  const out = document.getElementById("cmp-out");
  out.innerHTML = loading("Aligning the sentences");
  let result;
  try {
    result = c.mode === "files" ? await post("/api/compare", { old: c.old, new: c.new }) : await post("/api/compare", { mode: "text", old_text: c.oldText, new_text: c.newText });
  } catch (error) {
    out.innerHTML = errorBox(error.message);
    return;
  }
  if (myTicket !== ticket) return;
  const n = result.counts;
  const real = n.CHANGED + n.ADDED + n.REMOVED;
  out.innerHTML = figures([
    [num(result.similarity, 2), "similarity", "document vectors"],
    [n.SAME, "kept"],
    [n.CHANGED, "edited"],
    [n.ADDED, "added"],
    [n.REMOVED, "removed"],
    [result["lexical lines flagged"], "plain diff flags", `against ${real} real changes`],
  ]) + `<div class="cols wide-left">${box("How the two relate", `<p class="relation">${esc(result.relation)}</p><p>${esc(result["relation meaning"])}.</p>
      <p class="note">Equivalence means the same facts. Inclusion means one sits fully inside the other. Overlap means both have something the other lacks. Alignment score ${num(result["alignment score"], 1)}.</p>`)}
      ${chartBox("cmp-outcomes", "What happened to each sentence")}</div>` +
    tabsBar(["Changes", "Side by side", "Words and numbers", "Copy check", "Alignment grid", "Timeline"], c.tab) + `<div id="cmp-tab"></div>`;
  plot("cmp-outcomes", [{ type: "bar", x: ["kept", "edited", "added", "removed"], y: [n.SAME, n.CHANGED, n.ADDED, n.REMOVED], marker: { color: ["#a39e92", "#9a6400", "#2e6a3e", "#a8361c"] }, text: [n.SAME, n.CHANGED, n.ADDED, n.REMOVED], textposition: "outside" }],
    { margin: { l: 30, r: 10, t: 20, b: 30 }, yaxis: { dtick: 1, range: [0, Math.max(n.SAME, n.CHANGED, n.ADDED, n.REMOVED, 1) * 1.3] } }, 230);
  bindTabs(out, (name) => {
    c.tab = name;
    showCompareTab(result, name);
  });
  showCompareTab(result, c.tab);
}

function showCompareTab(result, name) {
  const area = document.getElementById("cmp-tab");
  const c = state.compare;
  if (name === "Changes") {
    const marks = { SAME: "=", CHANGED: "~", ADDED: "+", REMOVED: "-" };
    const lines = result.steps.filter((step) => c.showSame || step.label !== "SAME").map((step) => {
      const text = step.label === "CHANGED" ? step.words : esc(step.label === "REMOVED" ? step.old : step.new);
      const value = step.label === "ADDED" || step.label === "REMOVED" ? "" : num(step.value, 2);
      return `<li class="${step.label.toLowerCase()}"><span class="g">${marks[step.label]}</span><div class="t">${text}</div><span class="v">${value}</span></li>`;
    }).join("");
    area.innerHTML = `<p class="legend"><b>=</b>same meaning <b>~</b>edited <b>+</b>added <b>-</b>removed. The number is the cosine similarity of the two sentences.</p>
      <p><label class="note"><input type="checkbox" id="cmp-same" ${c.showSame ? "checked" : ""}> show sentences that did not change</label></p>
      <ul class="diff">${lines || '<li><span class="g"></span><div class="t empty">No differences.</div><span></span></li>'}</ul>`;
    document.getElementById("cmp-same").addEventListener("change", (event) => {
      c.showSame = event.target.checked;
      showCompareTab(result, name);
    });
  }
  if (name === "Side by side") {
    area.innerHTML = `<div class="table-wrap"><div class="pair head"><div>First</div><div>Second</div></div>${result.steps
      .map((step) => `<div class="pair ${step.label.toLowerCase()}"><div>${esc(step.old)}</div><div>${esc(step.new)}</div></div>`).join("")}</div>`;
  }
  if (name === "Words and numbers") {
    area.innerHTML = `<div class="cols">
      <div>${box("Keywords only in the first", tags(result["keywords only in old"], "no"))}${box("Numbers that disappeared", tags(result["numbers removed"], "no"))}${box("Skills that disappeared", tags(result["skills removed"], "no"))}</div>
      <div>${box("Keywords only in the second", tags(result["keywords only in new"], "ok"))}${box("Numbers that appeared", tags(result["numbers added"], "ok"))}${box("Skills that appeared", tags(result["skills added"], "ok"))}</div>
    </div>${box("Keywords both share", tags(result["shared keywords"], "mark"))}`;
  }
  if (name === "Copy check") {
    const copy = result.copy;
    area.innerHTML = figures([
      [percent(copy.jaccard), "overlap", "shared 4 word runs"],
      [percent(copy["A found in B"]), "first inside second"],
      [percent(copy["B found in A"]), "second inside first"],
    ]) + box("Exact phrases found in both", tags(copy["shared phrases"], "warn"));
  }
  if (name === "Alignment grid") {
    const a = result.alignment;
    if (!a) {
      area.innerHTML = `<p class="empty">The grid is only drawn for documents with up to about 80 sentences each.</p>`;
      return;
    }
    area.innerHTML = chartBox("cmp-grid", "Needleman-Wunsch score grid", "Each cell holds the best score so far. The red line is the traceback: diagonal steps match sentences, right steps add, down steps remove.");
    const xs = ["gap", ...a.columns.map((s, i) => `${i + 1}. ${short(s, 22)}`)];
    const ys = ["gap", ...a.rows.map((s, i) => `${i + 1}. ${short(s, 22)}`)];
    plot("cmp-grid", [
      { type: "heatmap", z: a.matrix, x: xs.map((_, i) => i), y: ys.map((_, i) => i), colorscale: [[0, "#f5e0d8"], [0.5, "#fffdf8"], [1, "#9fb0c6"]], texttemplate: "%{z:.1f}", textfont: { size: 9 }, showscale: false, hovertemplate: "score %{z}<extra></extra>" },
      { type: "scatter", mode: "lines+markers", x: a.path.map((p) => p[1]), y: a.path.map((p) => p[0]), line: { color: "#a8361c", width: 3 }, marker: { size: 6, color: "#a8361c" }, hoverinfo: "skip" },
    ], { showlegend: false, margin: { l: 10, r: 10, t: 10, b: 10 }, xaxis: { tickvals: xs.map((_, i) => i), ticktext: xs, tickangle: 40, side: "top" }, yaxis: { tickvals: ys.map((_, i) => i), ticktext: ys, autorange: "reversed" } },
    Math.max(420, 32 * ys.length + 170));
  }
  if (name === "Timeline") {
    const rows = result.timeline;
    if (!rows.length) {
      area.innerHTML = `<p class="empty">These two files are not part of a detected version group. Name files like report_v1 and report_v2 to see how a document changed over time.</p>`;
      return;
    }
    area.innerHTML = chartBox("cmp-time", "How the document changed over time", "Bars count changes between neighbouring versions. The line shows similarity.");
    const steps = rows.map((row) => `${short(row.from, 16)} to ${short(row.to, 16)}`);
    plot("cmp-time", [
      { type: "bar", name: "edited", x: steps, y: rows.map((r) => r.CHANGED), marker: { color: "#9a6400" } },
      { type: "bar", name: "added", x: steps, y: rows.map((r) => r.ADDED), marker: { color: "#2e6a3e" } },
      { type: "bar", name: "removed", x: steps, y: rows.map((r) => r.REMOVED), marker: { color: "#a8361c" } },
      { type: "scatter", mode: "lines+markers", name: "similarity", x: steps, y: rows.map((r) => r.similarity), yaxis: "y2", line: { color: "#1f3a5f", width: 3 } },
    ], { barmode: "stack", yaxis2: { overlaying: "y", side: "right", range: [0, 1], showgrid: false } }, 360);
  }
}

async function matchPage(myTicket) {
  const all = names();
  const roles = state.roles;
  if (!state.match || !all.includes(state.match.job)) {
    const job = roles.job_file || all[0];
    const resumes = roles.resume_files.filter((name) => name !== job);
    state.match = { job, resumes: resumes.length ? resumes : all.filter((name) => name !== job).slice(0, 3), jobText: "" };
  }
  const m = state.match;
  m.resumes = m.resumes.filter((name) => all.includes(name) && name !== m.job);
  const candidates = all.filter((name) => name !== m.job);
  const tools = `<label class="field">Job description${select("match-job", all, m.job)}</label>
    <div class="field">Resumes to rank${checks("match-resume", candidates, m.resumes)}</div>
    <button id="match-run" class="btn">Rank the resumes</button>
    <details class="fold" style="flex-basis:100%"><summary>Use a different job description text</summary><textarea id="match-text" class="input" rows="4" placeholder="Paste a job description to use instead of the file">${esc(m.jobText)}</textarea></details>`;
  main.innerHTML = head("04", "Match resumes", "Skills are pulled out with POS tags, a skill list and vector similarity, then compared with what the job asks for. Names, emails, phone numbers and gender words are removed before scoring.", tools) + `<div id="match-out"></div>`;
  document.getElementById("match-job").addEventListener("change", (event) => {
    m.job = event.target.value;
    m.resumes = checked("match-resume");
    route();
  });
  document.getElementById("match-run").addEventListener("click", () => {
    m.resumes = checked("match-resume");
    m.jobText = document.getElementById("match-text").value;
    runMatch(ticket);
  });
  if (m.resumes.length) runMatch(myTicket);
  else document.getElementById("match-out").innerHTML = `<p class="empty">Tick at least one resume and press the button.</p>`;
}

async function runMatch(myTicket) {
  const m = state.match;
  const out = document.getElementById("match-out");
  if (!m.resumes.length) {
    out.innerHTML = `<p class="empty">Tick at least one resume.</p>`;
    return;
  }
  out.innerHTML = loading("Scoring the resumes");
  let data;
  try {
    data = await post("/api/match", { job: m.job, resumes: m.resumes, job_text: m.jobText });
  } catch (error) {
    out.innerHTML = errorBox(error.message);
    return;
  }
  if (myTicket !== ticket) return;
  const order = data.ordered;
  const results = data.results;
  const best = order[0];
  const average = order.reduce((sum, name) => sum + results[name].final_score, 0) / order.length;
  const needed = data.job_skills;
  out.innerHTML = figures([
    [order.length, "candidates"],
    [short(best, 22), "best match", `score ${num(results[best].final_score, 2)}`, true],
    [needed.length, "skills asked for"],
    [num(average, 2), "average score"],
  ]) + box("What the job asks for", tags(needed, "mark", "no skills from the list were found, so matching uses requirement coverage")) +
    `<div class="cols wide-left">${chartBox("match-bars", "Ranking, and where each score comes from", needed.length ? "Skills count for 60%, requirement coverage 25%, overall text similarity 15%." : "Coverage counts for 60%, text similarity 40%.")}
      ${chartBox("match-radar", "Candidate profiles")}</div>` +
    (needed.length ? chartBox("match-grid", "Who has which skill", "Green means the skill was found in the resume.") : "") +
    section("Each candidate") +
    order.map((name, index) => candidateCard(name, index + 1, results[name], data.read_text[name])).join("") +
    section("Fairness check", "same resume, different name") +
    `<p class="note">Each resume is scored again with another name and with gender words swapped. A fair matcher gives exactly the same score.</p>
     <p><button id="fair-run" class="btn quiet">Run the fairness check</button></p><div id="fair-out"></div>`;

  const parts = needed.length
    ? [["skills", 0.6, "skill_score", "#1f3a5f"], ["requirements", 0.25, "coverage", "#2e6a3e"], ["text", 0.15, "text_score", "#9a6400"]]
    : [["requirements", 0.6, "coverage", "#2e6a3e"], ["text", 0.4, "text_score", "#9a6400"]];
  const reversed = [...order].reverse();
  plot("match-bars", parts.map(([label, weight, key, colour]) => ({
    type: "bar", orientation: "h", name: label, x: reversed.map((name) => weight * results[name][key]), y: reversed.map((name) => short(name, 24)), marker: { color: colour },
    hovertemplate: "%{y}<br>" + label + ": %{x:.2f}<extra></extra>",
  })), { barmode: "stack", margin: { l: 10, r: 20, t: 10, b: 40 } }, Math.max(260, 50 * order.length + 100));

  const axes = ["Skill match", "Requirement coverage", "Text similarity", "Skill breadth"];
  const widest = Math.max(...order.map((name) => Object.keys(results[name].evidence).length), 1);
  plot("match-radar", order.map((name) => {
    const r = results[name];
    const values = [r.skill_score, r.coverage, r.text_score, Object.keys(r.evidence).length / widest];
    return { type: "scatterpolar", fill: "toself", name: short(name, 20), r: [...values, values[0]], theta: [...axes, axes[0]], opacity: 0.6 };
  }), { polar: { bgcolor: "rgba(0,0,0,0)", radialaxis: { range: [0, 1], showticklabels: false, gridcolor: "#e8e2d5" }, angularaxis: { gridcolor: "#e8e2d5" } }, margin: { l: 40, r: 40, t: 20, b: 20 } }, Math.max(260, 50 * order.length + 100));

  if (needed.length) {
    plot("match-grid", [{
      type: "heatmap", z: order.map((name) => needed.map((skill) => (results[name].matched.includes(skill) ? 1 : 0))), x: needed, y: order.map((name) => short(name, 24)),
      colorscale: [[0, "#f5e0d8"], [1, "#2e6a3e"]], zmin: 0, zmax: 1, showscale: false, xgap: 2, ygap: 2, hovertemplate: "%{y}<br>%{x}<extra></extra>",
    }], { margin: { l: 10, r: 10, t: 10, b: 10 }, xaxis: { tickangle: 35 }, yaxis: { autorange: "reversed" } }, 130 + 42 * order.length);
  }

  document.getElementById("fair-run").addEventListener("click", async () => {
    const target = document.getElementById("fair-out");
    target.innerHTML = loading("Scoring the changed resumes");
    try {
      const rows = await post("/api/fairness", { job: state.match.job, resumes: order });
      const fair = rows.every((row) => row.fair);
      target.innerHTML = `<p>${fair ? tag("every score stayed the same", "ok") : tag("some scores moved, have a look", "no")}</p>` + table(rows, [
        { key: "resume", label: "Resume" }, { key: "original score", label: "Score", kind: "num", digits: 3 }, { key: "name used in test", label: "Name used" },
        { key: "score after swap", label: "After swap", kind: "num", digits: 3 }, { key: "difference", label: "Difference", kind: "num", digits: 4 }, { key: "fair", label: "Fair" },
      ]);
    } catch (error) {
      target.innerHTML = errorBox(error.message);
    }
  });
}

function candidateCard(name, rank, r, readText) {
  const evidence = Object.entries(r.evidence).map(([skill, found]) => ({ skill, found }));
  return `<details class="candidate"${rank === 1 ? " open" : ""}><summary><span class="rank">${rank}</span><span class="who">${esc(name)}</span>
      <span class="score">score ${num(r.final_score, 2)} &nbsp; skills ${num(r.skill_score, 2)} &nbsp; coverage ${num(r.coverage, 2)}</span></summary>
    <div class="inside">
      <div class="cols"><div>
        <p><b>Has</b><br>${tags(r.matched, "ok")}</p>
        <p><b>Missing</b><br>${tags(r.missing, "no")}</p>
        <p><b>Also has</b><br>${tags(r.extra, "mark")}</p>
        ${r.rejected.length ? `<p><b>False matches the POS filter blocked</b><br>${tags(r.rejected, "warn")}</p>` : ""}
      </div><div>${table(evidence, [{ key: "skill", label: "Skill" }, { key: "found", label: "Found as" }])}</div></div>
      ${table(r.coverage_rows, [{ key: "requirement", label: "Requirement in the job" }, { key: "best resume line", label: "Closest line in the resume" }, { key: "score", label: "Match", kind: "meter", max: 1 }])}
      <details class="fold"><summary>What the matcher actually read</summary><div class="plain-text">${esc(readText)}</div></details>
    </div></details>`;
}

async function summaryPage(myTicket) {
  const all = names();
  const roles = state.roles;
  if (!state.summary || state.summary.files.some((name) => !all.includes(name))) {
    state.summary = { files: roles.summary_groups[0] || all.slice(0, 1), size: 4, reference: roles.reference_file || "", referenceText: "" };
  }
  const s = state.summary;
  const tools = `<div class="field">Documents to summarise${checks("sum-file", all, s.files)}</div>
    <div class="field" style="max-width:340px">
      <label class="field">Length <output id="sum-size-out">${s.size} sentences</output><input id="sum-size" type="range" min="1" max="10" value="${s.size}"></label>
      <label class="field">Compare against${select("sum-ref", [["", "nothing"], ...all.map((name) => [name, name])], s.reference)}</label>
      <button id="sum-run" class="btn">Summarise</button>
    </div>
    <details class="fold" style="flex-basis:100%"><summary>Paste a reference summary instead</summary><textarea id="sum-ref-text" class="input" rows="3" placeholder="A summary written by a person, used for ROUGE">${esc(s.referenceText)}</textarea></details>`;
  main.innerHTML = head("05", "Summarise", "TextRank ranks the sentences on a similarity graph, near repeats are dropped, and a few rewrite rules tighten the result. Every sentence keeps a note of where it came from.", tools) + `<div id="sum-out"></div>`;
  const slider = document.getElementById("sum-size");
  slider.addEventListener("input", () => (document.getElementById("sum-size-out").textContent = `${slider.value} sentences`));
  document.getElementById("sum-run").addEventListener("click", () => {
    s.files = checked("sum-file");
    s.size = Number(slider.value);
    s.reference = document.getElementById("sum-ref").value;
    s.referenceText = document.getElementById("sum-ref-text").value;
    runSummary(ticket);
  });
  runSummary(myTicket);
}

async function runSummary(myTicket) {
  const s = state.summary;
  const out = document.getElementById("sum-out");
  if (!s.files.length) {
    out.innerHTML = `<p class="empty">Tick at least one document.</p>`;
    return;
  }
  out.innerHTML = loading("Picking the important sentences");
  let data;
  try {
    data = await post("/api/summary", { files: s.files, size: s.size, reference: s.reference, reference_text: s.referenceText });
  } catch (error) {
    out.innerHTML = errorBox(error.message);
    return;
  }
  if (myTicket !== ticket) return;
  const sources = [...new Set(data.trace.map((t) => t.source))];
  const text = data.trace.map((t) => `${esc(t.sentence)}<sup>${sources.indexOf(t.source) + 1}</sup>`).join(" ");
  out.innerHTML = figures([
    [num(data.source_words), "source words", `${s.files.length} documents`],
    [num(data.summary_words), "summary words"],
    [percent(1 - data.summary_words / Math.max(data.source_words, 1)), "shorter"],
    [sources.length, "sources quoted"],
  ]) + `<div class="box"><h3>Summary</h3><p class="summary-text">${text || '<span class="empty">Nothing to summarise.</span>'}</p>
      <ol class="footnotes">${sources.map((source) => `<li>${esc(source)}</li>`).join("")}</ol></div>
    ${box("The same summary with the rewrite rules applied", `<p>${esc(data.summary)}</p>`)}
    ${table(data.trace, [{ key: "sentence", label: "Evidence sentence" }, { key: "source", label: "From" }, { key: "score", label: "Importance", kind: "meter", max: 1 }])}
    ${data.evaluation ? chartBox("sum-rouge", "How close it is to the reference", "ROUGE counts shared words and word pairs. The vector score compares meaning sentence by sentence.") : `<p class="note">Pick or paste a reference summary above to get ROUGE scores.</p>`}
    ${section("Every document in two sentences")}<p><button id="sum-singles" class="btn quiet">Show them</button></p><div id="sum-singles-out"></div>`;
  if (data.evaluation) {
    const metrics = data.evaluation.map((row) => row.metric);
    plot("sum-rouge", ["precision", "recall", "f1"].map((measure, index) => ({
      type: "bar", name: measure, x: metrics, y: data.evaluation.map((row) => row[measure]), marker: { color: ["#9fb0c6", "#1f3a5f", "#a8361c"][index] },
      text: data.evaluation.map((row) => row[measure].toFixed(2)), textposition: "outside",
    })), { barmode: "group", yaxis: { range: [0, 1.1] } }, 340);
  }
  document.getElementById("sum-singles").addEventListener("click", async () => {
    const target = document.getElementById("sum-singles-out");
    target.innerHTML = loading("Summarising each file");
    try {
      const rows = await get("/api/singles");
      target.innerHTML = table(rows, [{ key: "document", label: "Document" }, { key: "summary", label: "Summary" }]);
    } catch (error) {
      target.innerHTML = errorBox(error.message);
    }
  });
}

async function askPage(myTicket) {
  const all = names();
  const last = state.history[0] || "";
  const tools = `<label class="field" style="flex:3 1 420px">Question<input id="ask-q" class="input" type="text" value="${esc(last)}" placeholder="Type a question about your documents"></label>
    <label class="field" style="flex:0 0 120px">Results${select("ask-k", ["3", "5", "8", "10"], "5")}</label>
    <button id="ask-run" class="btn">Ask</button>
    <details class="fold" style="flex-basis:100%"><summary>Only search some documents</summary>${checks("ask-only", all, [])}</details>`;
  main.innerHTML = head("06", "Ask a question", "The question is turned into a vector and compared with every sentence. For how many, when, who and where questions a short answer is cut out of the best sentence.", tools) +
    `<div class="cols wide-left"><div id="ask-out"></div><div>${box("Try one of these", `<ul class="links" id="ask-examples"><li class="empty">loading</li></ul>`)}<div id="ask-history"></div></div></div>`;
  const input = document.getElementById("ask-q");
  const run = () => runAsk(ticket);
  document.getElementById("ask-run").addEventListener("click", run);
  input.addEventListener("keydown", (event) => event.key === "Enter" && run());
  renderHistory();
  try {
    const examples = await get("/api/examples");
    if (myTicket !== ticket) return;
    document.getElementById("ask-examples").innerHTML = examples.map((q) => `<li><button type="button">${esc(q)}</button></li>`).join("");
    document.querySelectorAll("#ask-examples button").forEach((button) => button.addEventListener("click", () => {
      input.value = button.textContent;
      run();
    }));
  } catch (error) {
    document.getElementById("ask-examples").innerHTML = `<li class="empty">${esc(error.message)}</li>`;
  }
  if (last) runAsk(myTicket);
  else document.getElementById("ask-out").innerHTML = `<p class="empty">Ask something, or pick an example on the right.</p>`;
}

function renderHistory() {
  const target = document.getElementById("ask-history");
  if (!target || state.history.length < 2) return;
  target.innerHTML = box("Asked before", `<ul class="links">${state.history.slice(1).map((q) => `<li><button type="button">${esc(q)}</button></li>`).join("")}</ul>`);
  target.querySelectorAll("button").forEach((button) => button.addEventListener("click", () => {
    document.getElementById("ask-q").value = button.textContent;
    runAsk(ticket);
  }));
}

async function runAsk(myTicket) {
  const question = document.getElementById("ask-q").value.trim();
  const out = document.getElementById("ask-out");
  if (!question) return;
  state.history = [question, ...state.history.filter((q) => q !== question)].slice(0, 8);
  renderHistory();
  out.innerHTML = loading("Searching");
  let a;
  try {
    a = await post("/api/ask", { question, top_k: Number(document.getElementById("ask-k").value), only: checked("ask-only") });
  } catch (error) {
    out.innerHTML = errorBox(error.message);
    return;
  }
  if (myTicket !== ticket) return;
  if (!a["answer sentence"]) {
    out.innerHTML = `<p class="empty">No sentence matched that question.</p>`;
    return;
  }
  const terms = {};
  a.terms.forEach((term) => (terms[term] = ""));
  out.innerHTML = `<div class="answer"><div>${tag(a["question type"].toLowerCase() + " question", "mark")}</div>
      ${a["short answer"] ? `<div class="short">${esc(a["short answer"])}</div>` : ""}
      <div class="said">${highlight(a["answer sentence"], terms)}</div>
      <div class="from">from ${esc(a.source)}, match ${num(a.score, 2)} <span class="meter"><i style="width:${Math.min(100, a.score * 100)}%"></i></span></div></div>
    ${a["other results"].length ? section("Other close sentences") + `<ul class="links">${a["other results"].map((r) => `<li>${highlight(r.text, terms)} <span class="note">${esc(r.source)}, ${num(r.score, 2)}</span></li>`).join("")}</ul>` : ""}`;
}

async function graphPage(myTicket) {
  const all = names();
  if (!state.graph || state.graph.files.some((name) => !all.includes(name))) {
    state.graph = { files: state.roles.summary_groups[0] || all };
  }
  const tools = `<div class="field">Documents to use${checks("graph-file", all, state.graph.files)}</div><button id="graph-run" class="btn">Draw the graph</button>`;
  main.innerHTML = head("07", "Knowledge graph", "POS tag patterns look for a noun phrase, then a verb phrase, then another noun phrase. Each match becomes a link: who or what does something to whom.", tools) + `<div id="graph-out"></div>`;
  document.getElementById("graph-run").addEventListener("click", () => {
    state.graph.files = checked("graph-file");
    runGraph(ticket);
  });
  runGraph(myTicket);
}

async function runGraph(myTicket) {
  const out = document.getElementById("graph-out");
  if (!state.graph.files.length) {
    out.innerHTML = `<p class="empty">Tick at least one document.</p>`;
    return;
  }
  out.innerHTML = loading("Finding subject, verb, object patterns");
  let g;
  try {
    g = await post("/api/graph", { files: state.graph.files });
  } catch (error) {
    out.innerHTML = errorBox(error.message);
    return;
  }
  if (myTicket !== ticket) return;
  if (!g.triples.length) {
    out.innerHTML = `<p class="empty">No subject, verb, object patterns were found in these documents.</p>`;
    return;
  }
  const most = [...g.nodes].sort((a, b) => b.degree - a.degree)[0];
  out.innerHTML = figures([[g.triples.length, "triples"], [g.nodes.length, "ideas"], [g.edges.length, "links"], [short(most.id, 20), "most connected", `${most.degree} links`, true]]) +
    chartBox("graph-plot", "Who does what", "Hover the small squares on the lines to read each relation.") + section("Every triple") +
    table(g.triples, [{ key: "document", label: "Document" }, { key: "subject", label: "Subject" }, { key: "relation", label: "Relation" }, { key: "object", label: "Object" }, { key: "sentence", label: "Sentence" }]);
  const place = {};
  g.nodes.forEach((node) => (place[node.id] = node));
  const lineX = [];
  const lineY = [];
  const midX = [];
  const midY = [];
  const midText = [];
  g.edges.forEach((edge) => {
    const a = place[edge.source];
    const b = place[edge.target];
    lineX.push(a.x, b.x, null);
    lineY.push(a.y, b.y, null);
    midX.push((a.x + b.x) / 2);
    midY.push((a.y + b.y) / 2);
    midText.push(`${edge.source} <b>${edge.label}</b> ${edge.target}`);
  });
  plot("graph-plot", [
    { type: "scatter", mode: "lines", x: lineX, y: lineY, line: { color: "#c9c1ae", width: 1.4 }, hoverinfo: "skip" },
    { type: "scatter", mode: "markers", x: midX, y: midY, text: midText, marker: { size: 7, symbol: "square", color: "#a8361c" }, hovertemplate: "%{text}<extra></extra>" },
    { type: "scatter", mode: "markers+text", x: g.nodes.map((n) => n.x), y: g.nodes.map((n) => n.y), text: g.nodes.map((n) => n.id), textposition: "top center", textfont: { size: 11, color: "#1d1c19" },
      marker: { size: g.nodes.map((n) => 10 + 5 * n.degree), color: "#1f3a5f", opacity: 0.85, line: { width: 2, color: "#fffdf8" } }, hovertemplate: "%{text}<extra></extra>" },
  ], { showlegend: false, margin: { l: 10, r: 10, t: 10, b: 10 }, xaxis: { visible: false }, yaxis: { visible: false } }, 600);
}

async function playgroundPage() {
  main.innerHTML = head("08", "NLP playground", "Small tools to try classic NLP on your own words. Nothing here needs a document.") +
    tabsBar(["Pipeline", "Word meanings", "Language", "Redaction", "Skill finder"], state.playgroundTab) + `<div id="play-tab"></div>`;
  bindTabs(main, (name) => {
    state.playgroundTab = name;
    showPlayTab(name);
  });
  showPlayTab(state.playgroundTab);
}

function playForm(id, label, value, multiline, button) {
  const field = multiline ? `<textarea id="${id}" class="input" rows="4">${esc(value)}</textarea>` : `<input id="${id}" class="input" type="text" value="${esc(value)}">`;
  return `<div class="row"><label class="field">${esc(label)}${field}</label><button id="${id}-go" class="btn">${esc(button)}</button></div><div id="${id}-out"></div>`;
}

function onPlay(id, handler) {
  const go = async () => {
    const out = document.getElementById(`${id}-out`);
    out.innerHTML = loading();
    try {
      await handler(document.getElementById(id).value, out);
    } catch (error) {
      out.innerHTML = errorBox(error.message);
    }
  };
  document.getElementById(`${id}-go`).addEventListener("click", go);
  go();
}

function showPlayTab(name) {
  const area = document.getElementById("play-tab");
  if (name === "Pipeline") {
    area.innerHTML = playForm("pp", "A sentence", "Sara Khan was building better dashboards for Google in London last year.", false, "Run the pipeline");
    onPlay("pp", async (text, out) => {
      const rows = await post("/api/pipeline", { text });
      out.innerHTML = box("Tokens and their tags", `<div class="tokens">${rows.map((row) => `<div class="token ${esc(row["POS tag"][0])}"><b>${esc(row.token)}</b><small>${esc(row["POS tag"])}</small></div>`).join("")}</div>
        <p class="note">Blue underline nouns, green verbs, amber adjectives, red adverbs.</p>`) + table(rows, [
        { key: "token", label: "Token" }, { key: "stopword", label: "Stopword" }, { key: "stem", label: "Stem" }, { key: "lemma", label: "Lemma" },
        { key: "POS tag", label: "Tag" }, { key: "meaning", label: "Meaning" }, { key: "entity", label: "Entity" }]);
    });
  }
  if (name === "Word meanings") {
    area.innerHTML = playForm("wm", "A word", "growth", false, "Look it up");
    onPlay("wm", async (text, out) => {
      const rows = await post("/api/meaning", { text });
      if (!rows.length) {
        out.innerHTML = `<p class="empty">WordNet does not know this word.</p>`;
        return;
      }
      const split = (key) => [...new Set(rows.flatMap((row) => row[key].split(",").map((v) => v.trim()).filter(Boolean)))];
      out.innerHTML = `<div class="cols">${box("Synonyms", tags(split("synonyms"), "ok"))}${box("Opposites", tags(split("opposites"), "no"))}</div>` +
        table(rows, [{ key: "type", label: "Type" }, { key: "meaning", label: "Meaning" }, { key: "broader idea", label: "Broader idea" }, { key: "example", label: "Example" }]);
    });
  }
  if (name === "Language") {
    area.innerHTML = playForm("lg", "Text in any language", "Le chat est sur la table et il dort avec le chien pendant que nous mangeons.", true, "Detect the language");
    onPlay("lg", async (text, out) => {
      const data = await post("/api/language", { text });
      if (!data) {
        out.innerHTML = "";
        return;
      }
      out.innerHTML = figures([[data.language, "language", `confidence ${num(data.confidence, 2)}`, true]]) + chartBox("lg-chart", "Stopwords shared with each language", "Every language has its own short, common words. The one with the most matches wins.");
      plot("lg-chart", [{ type: "bar", x: data.scores.map((s) => s[0]), y: data.scores.map((s) => s[1]), marker: { color: data.scores.map((s, i) => (i === 0 ? "#a8361c" : "#9fb0c6")) } }], {}, 300);
    });
  }
  if (name === "Redaction") {
    const all = names();
    const options = [["", "the text below"], ...all.map((n) => [n, n])];
    const chosen = all.find((n) => /resume|cv/i.test(n)) || "";
    area.innerHTML = `<div class="row"><label class="field">Redact${select("rd-doc", options, chosen)}</label></div>` +
      playForm("rd", "Text", "Name: John Smith\nEmail: john@mail.com\nPhone: +91 98765 43210\nJohn has worked in Pune for five years.", true, "Hide personal details");
    onPlay("rd", async (text, out) => {
      const data = await post("/api/redact", { text, name: document.getElementById("rd-doc").value });
      const counts = Object.entries(data.counts).map(([k, v]) => `${k.toLowerCase()}: ${v}`);
      out.innerHTML = `<p>${tags(counts, "warn", "nothing to hide")}</p><div class="cols">${box("Before", `<div class="plain-text">${esc(data.original)}</div>`)}${box("After", `<div class="plain-text">${esc(data.redacted)}</div>`)}</div>
        <button id="rd-save" class="btn quiet small">Download the redacted text</button>`;
      document.getElementById("rd-save").addEventListener("click", () => downloadText(data.redacted, "redacted.txt"));
    });
  }
  if (name === "Skill finder") {
    area.innerHTML = playForm("sk", "Any text that mentions skills", "I build REST APIs in Python, use Docker and AWS, and I like frontend scripting. We hand-polish every screen.", true, "Find skills");
    onPlay("sk", async (text, out) => {
      const data = await post("/api/skills", { text });
      const rows = Object.entries(data.found).map(([skill, found]) => ({ skill, found }));
      out.innerHTML = box("Skills found", tags(rows.map((r) => r.skill), "ok")) + (data.rejected.length ? box("Blocked by the POS filter", tags(data.rejected, "warn")) : "") +
        table(rows, [{ key: "skill", label: "Skill" }, { key: "found", label: "Found as" }]);
    });
  }
}

async function qualityPage(myTicket) {
  const top = head("09", "Quality checks", "Is the vocabulary drifting between versions, which file is the odd one out, did any file copy from another, and do the built in tests still pass.");
  main.innerHTML = top + loading("Running the checks");
  const data = await get("/api/quality?threshold=0.8");
  if (myTicket !== ticket) return;
  const drifted = data.drift.some((row) => row.drift);
  main.innerHTML = top + `<div class="cols">
      <div>${section("Drift between versions", "Jensen-Shannon distance")}
        ${data.drift.length ? table(data.drift, [{ key: "check", label: "Versions" }, { key: "distance", label: "Distance", kind: "num", digits: 3 }, { key: "new word ratio", label: "New words", kind: "num", digits: 3 }, { key: "drift", label: "Drift" }]) +
          `<p>${drifted ? tag("drift found, retrain the vectorizer", "no") : tag("no drift, the model is fine", "ok")}</p>` : `<p class="empty">No version groups were found.</p>`}</div>
      <div>${section("The odd one out")}${chartBox("q-unusual", "Distance of each file from all the others", "Higher means its vocabulary is unlike the rest.")}</div>
    </div>
    ${section("Copied sentences between different files")}
    <div class="row"><label class="field" style="max-width:320px">Similarity needed <output id="q-th-out">0.80</output><input id="q-th" type="range" min="0.5" max="1" step="0.05" value="0.8"></label><button id="q-th-go" class="btn quiet">Check again</button></div>
    <div id="q-shared">${sharedTable(data.shared)}</div>
    ${section("Built in tests and speed")}<p><button id="q-tests" class="btn">Run the tests</button></p><div id="q-tests-out"></div>`;
  const rows = [...data.unusual].reverse();
  plot("q-unusual", [{ type: "bar", orientation: "h", x: rows.map((r) => r["distance from the rest"]), y: rows.map((r) => short(r.document, 24)), marker: { color: rows.map((r, i) => (i === rows.length - 1 ? "#a8361c" : "#9fb0c6")) } }],
    { margin: { l: 10, r: 20, t: 10, b: 40 } }, Math.max(260, 26 * rows.length + 60));
  const range = document.getElementById("q-th");
  range.addEventListener("input", () => (document.getElementById("q-th-out").textContent = Number(range.value).toFixed(2)));
  document.getElementById("q-th-go").addEventListener("click", async () => {
    const target = document.getElementById("q-shared");
    target.innerHTML = loading("Comparing every sentence");
    try {
      const again = await get(`/api/quality?threshold=${range.value}`);
      target.innerHTML = sharedTable(again.shared);
    } catch (error) {
      target.innerHTML = errorBox(error.message);
    }
  });
  document.getElementById("q-tests").addEventListener("click", async () => {
    const target = document.getElementById("q-tests-out");
    target.innerHTML = loading("Running");
    try {
      const result = await post("/api/tests", {});
      const passed = result.tests.filter((t) => t.result === "PASSED").length;
      const slowest = [...result.benchmark].sort((a, b) => b["average ms"] - a["average ms"])[0];
      target.innerHTML = figures([[`${passed} of ${result.tests.length}`, "tests passed", "", true], [slowest.task, "slowest task", `${num(slowest["average ms"], 0)} ms`, true]]) +
        `<div class="cols">${table(result.tests, [{ key: "test", label: "Test" }, { key: "result", label: "Result", render: (v) => tag(v.toLowerCase(), v === "PASSED" ? "ok" : "no") }, { key: "time ms", label: "ms", kind: "num", digits: 1 }])}
        ${chartBox("q-bench", "Average time per task", "Milliseconds, three runs each.")}</div>`;
      plot("q-bench", [{ type: "bar", x: result.benchmark.map((b) => b.task), y: result.benchmark.map((b) => b["average ms"]), marker: { color: "#1f3a5f" } }], { xaxis: { tickangle: 25 } }, 300);
    } catch (error) {
      target.innerHTML = errorBox(error.message);
    }
  });
}

function sharedTable(rows) {
  if (!rows.length) return `<p>${tag("no copied sentences found", "ok")}</p>`;
  return table(rows, [{ key: "similarity", label: "Similarity", kind: "num", digits: 2 }, { key: "document A", label: "File" }, { key: "sentence A", label: "Sentence" }, { key: "document B", label: "Other file" }, { key: "sentence B", label: "Similar sentence" }]);
}

function exportPage() {
  main.innerHTML = head("10", "Report and export", "Take the results with you. The PDF is built with ReportLab and takes a few seconds for many files.") +
    `<div class="cols three">
      ${box("PDF report", `<p>Overview table, similarity heatmap, entities, skills, resume ranking with the fairness check, colour coded version changes, summaries, drift and test results.</p><a class="btn" href="/api/report">Download the PDF</a>`)}
      ${box("Spreadsheet", `<p>One row per document with its type, language, length, readability, mood and keywords.</p><a class="btn quiet" href="/api/export.csv">Download CSV</a>`)}
      ${box("Everything as JSON", `<p>Roles, the overview, keywords, key phrases, skills and a short summary for every document.</p><a class="btn quiet" href="/api/export.json">Download JSON</a>`)}
    </div>`;
}

const RENDERERS = {
  overview: overviewPage,
  read: readPage,
  compare: comparePage,
  match: matchPage,
  summary: summaryPage,
  ask: askPage,
  graph: graphPage,
  playground: playgroundPage,
  quality: qualityPage,
  export: exportPage,
};

function renderNav(current) {
  document.getElementById("nav").innerHTML = PAGES.map(([key, label], index) =>
    `<a href="#${key}" class="${key === current ? "on" : ""}"><span>${String(index + 1).padStart(2, "0")}</span>${esc(label)}</a>`).join("");
}

async function route() {
  const page = RENDERERS[location.hash.slice(1)] ? location.hash.slice(1) : "overview";
  renderNav(page);
  const myTicket = ++ticket;
  if (!state.documents.length && page !== "playground") {
    welcome();
    return;
  }
  try {
    await RENDERERS[page](myTicket);
  } catch (error) {
    if (myTicket === ticket) main.innerHTML += errorBox(error.message);
  }
  if (myTicket === ticket) main.insertAdjacentHTML("beforeend", `<footer class="foot">Document Scanner. NLTK, scikit-learn, NumPy, ReportLab and Plotly. No AI service, no API keys.</footer>`);
}

function renderFiles() {
  document.getElementById("doc-count").textContent = state.documents.length;
  document.getElementById("file-list").innerHTML = state.documents.map((doc) =>
    `<li><span class="fname" title="${esc(doc.name)}"><span class="ftype">${esc(doc.type)}</span>${esc(doc.name)}</span><button type="button" data-name="${esc(doc.name)}" title="Remove this document">remove</button></li>`).join("");
  document.querySelectorAll("#file-list button").forEach((button) => button.addEventListener("click", async () => {
    await api(`/api/documents/${encodeURIComponent(button.dataset.name)}`, { method: "DELETE" });
    await refresh();
  }));
}

async function refresh() {
  const data = await get("/api/state");
  state.documents = data.documents;
  state.roles = data.roles;
  state.settings = data.settings;
  state.compare = null;
  state.match = null;
  state.summary = null;
  state.graph = null;
  renderFiles();
  const s = data.settings;
  [["set-skill", "out-skill", s.skill_threshold], ["set-version", "out-version", s.version_similarity], ["set-topic", "out-topic", s.topic_similarity]].forEach(([input, output, value]) => {
    document.getElementById(input).value = value;
    document.getElementById(output).textContent = Number(value).toFixed(2);
  });
  route();
}

async function uploadFiles(files) {
  if (!files.length) return;
  const form = new FormData();
  [...files].forEach((file) => form.append("files", file));
  toast(`Reading ${files.length} file${files.length > 1 ? "s" : ""}...`);
  try {
    const result = await api("/api/upload", { method: "POST", body: form });
    const parts = [];
    if (result.added.length) parts.push(`Added ${result.added.length}: ${result.added.join(", ")}`);
    if (result.skipped.length) parts.push(`Skipped ${result.skipped.join("; ")}`);
    toast(parts.join(". ") || "Nothing was added.", !result.added.length);
    await refresh();
  } catch (error) {
    toast(error.message, true);
  }
}

function setUpSidebar() {
  const input = document.getElementById("file-input");
  const drop = document.getElementById("drop");
  input.addEventListener("change", () => {
    uploadFiles(input.files);
    input.value = "";
  });
  ["dragenter", "dragover"].forEach((type) => drop.addEventListener(type, (event) => {
    event.preventDefault();
    drop.classList.add("over");
  }));
  ["dragleave", "drop"].forEach((type) => drop.addEventListener(type, (event) => {
    event.preventDefault();
    drop.classList.remove("over");
  }));
  drop.addEventListener("drop", (event) => uploadFiles(event.dataTransfer.files));

  document.getElementById("paste-add").addEventListener("click", async () => {
    const text = document.getElementById("paste-text").value;
    try {
      await post("/api/paste", { name: document.getElementById("paste-name").value, text });
      document.getElementById("paste-text").value = "";
      toast("Text added as a document.");
      await refresh();
    } catch (error) {
      toast(error.message, true);
    }
  });

  [["set-skill", "out-skill"], ["set-version", "out-version"], ["set-topic", "out-topic"]].forEach(([input, output]) => {
    const range = document.getElementById(input);
    range.addEventListener("input", () => (document.getElementById(output).textContent = Number(range.value).toFixed(2)));
  });
  document.getElementById("settings-apply").addEventListener("click", async () => {
    await post("/api/settings", {
      skill_threshold: document.getElementById("set-skill").value,
      version_similarity: document.getElementById("set-version").value,
      topic_similarity: document.getElementById("set-topic").value,
    });
    toast("Settings applied.");
    await refresh();
  });

  document.getElementById("clear-all").addEventListener("click", async () => {
    if (!state.documents.length || !confirm("Remove every document from this session?")) return;
    await post("/api/clear", {});
    await refresh();
  });
}

window.addEventListener("hashchange", route);
setUpSidebar();
refresh().catch((error) => {
  main.innerHTML = errorBox(`Could not reach the server. Is server.py running? (${error.message})`);
});
