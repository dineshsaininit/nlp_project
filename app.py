import re
import json
import hashlib
import pandas as pd
import networkx as nx
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from xml.sax.saxutils import escape
import nlp_engine as engine

st.set_page_config(page_title="NLP Document Scanner", layout="wide", initial_sidebar_state="expanded")

COLORS = ["#4f46e5", "#0ea5e9", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899", "#14b8a6", "#64748b", "#84cc16"]
px.defaults.template = "plotly_white"
px.defaults.color_discrete_sequence = COLORS
PAGES = ["Dashboard", "Document Explorer", "Compare Documents", "Resume Matcher", "Summarizer", "Ask Questions",
         "Knowledge Graph", "NLP Playground", "Quality and Drift", "Report and Export"]
PAGE_NOTES = {
    "Dashboard": "Everything at a glance",
    "Document Explorer": "Deep dive into one file",
    "Compare Documents": "Semantic diff with Needleman-Wunsch",
    "Resume Matcher": "Competence based ranking",
    "Summarizer": "Multi document summary",
    "Ask Questions": "Semantic search and answers",
    "Knowledge Graph": "Who does what to whom",
    "NLP Playground": "Try NLP on your own text",
    "Quality and Drift": "Tests, drift and copies",
    "Report and Export": "PDF, CSV and JSON",
}

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
html, body, [class*="css"], .stMarkdown, .stText, button, input, textarea { font-family: 'Inter', sans-serif; }
.block-container { padding-top: 3.2rem; padding-bottom: 3rem; max-width: 1320px; }
#MainMenu, footer { visibility: hidden; }
[data-testid="stSidebar"] { background: linear-gradient(180deg, #1e1b4b 0%, #312e81 55%, #4338ca 100%); }
[data-testid="stSidebar"] * { color: #e0e7ff; }
[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] { background: rgba(255,255,255,0.07); border: 1px dashed rgba(255,255,255,0.35); }
[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] * { color: #e0e7ff !important; }
[data-testid="stSidebar"] button { background: rgba(255,255,255,0.14) !important; border: 1px solid rgba(255,255,255,0.3) !important; color: #fff !important; }
[data-testid="stSidebar"] div[role="radiogroup"] label { padding: 7px 12px; border-radius: 10px; width: 100%; transition: background .15s ease; }
[data-testid="stSidebar"] div[role="radiogroup"] label:hover { background: rgba(255,255,255,0.10); }
[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) { background: rgba(255,255,255,0.20); box-shadow: inset 3px 0 0 #38bdf8; }
[data-testid="stSidebar"] hr { border-color: rgba(255,255,255,0.18); }
.brand { display: flex; align-items: center; gap: 12px; margin: 4px 0 18px; }
.brand .logo { width: 44px; height: 44px; border-radius: 12px; background: linear-gradient(135deg, #38bdf8, #a78bfa); display: flex; align-items: center; justify-content: center; font-weight: 800; color: #1e1b4b !important; font-size: 1.05rem; box-shadow: 0 6px 18px rgba(56,189,248,.35); }
.brand .name { font-weight: 800; font-size: 1.1rem; color: #fff !important; }
.brand .sub { font-size: .76rem; opacity: .75; }
.side-note { font-size: .78rem; opacity: .75; line-height: 1.4; }
.hero { background: linear-gradient(120deg, #4f46e5 0%, #7c3aed 45%, #0ea5e9 100%); border-radius: 22px; padding: 26px 32px; color: white; box-shadow: 0 14px 34px rgba(79,70,229,.28); margin-bottom: 20px; position: relative; overflow: hidden; }
.hero h1 { color: #fff; font-size: 2rem; font-weight: 800; margin: 0; line-height: 1.2; }
.hero p { color: rgba(255,255,255,.9); margin: 8px 0 0; font-size: 1rem; max-width: 820px; }
.hero .tag { display: inline-block; background: rgba(255,255,255,.18); padding: 4px 12px; border-radius: 999px; font-size: .72rem; font-weight: 700; letter-spacing: .08em; margin-bottom: 10px; }
.hero::before { content: ""; position: absolute; right: -70px; top: -90px; width: 260px; height: 260px; border-radius: 50%; background: rgba(255,255,255,.09); }
.hero::after { content: ""; position: absolute; right: 120px; bottom: -110px; width: 200px; height: 200px; border-radius: 50%; background: rgba(255,255,255,.06); }
.card-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 14px; margin: 4px 0 18px; }
.metric-card { background: #fff; border-radius: 16px; padding: 15px 17px; box-shadow: 0 2px 14px rgba(30,27,75,.07); border: 1px solid #eef0f6; border-top: 4px solid var(--accent); transition: transform .15s ease, box-shadow .15s ease; }
.metric-card:hover { transform: translateY(-2px); box-shadow: 0 8px 22px rgba(30,27,75,.12); }
.metric-card .label { font-size: .72rem; color: #6b7280; font-weight: 700; text-transform: uppercase; letter-spacing: .06em; }
.metric-card .value { font-size: 1.45rem; font-weight: 800; color: #1f2333; margin-top: 4px; word-break: break-word; }
.metric-card .hint { font-size: .78rem; color: #9ca3af; margin-top: 2px; }
.section-title { font-size: 1.12rem; font-weight: 800; color: #1f2333; margin: 22px 0 10px; display: flex; align-items: center; gap: 10px; }
.section-title::before { content: ""; width: 6px; height: 20px; border-radius: 3px; background: linear-gradient(#4f46e5, #0ea5e9); }
.panel { background: #fff; border-radius: 16px; padding: 16px 20px; border: 1px solid #eef0f6; box-shadow: 0 2px 14px rgba(30,27,75,.05); margin-bottom: 14px; line-height: 1.6; color: #1f2333; }
.panel h4 { margin: 0 0 8px; font-size: .95rem; color: #4338ca; }
.chip { display: inline-block; padding: 4px 11px; margin: 3px 5px 3px 0; border-radius: 999px; font-size: .8rem; font-weight: 600; }
.chip.good { background: #dcfce7; color: #166534; }
.chip.bad { background: #fee2e2; color: #991b1b; }
.chip.info { background: #e0e7ff; color: #3730a3; }
.chip.warn { background: #fef3c7; color: #92400e; }
.chip.plain { background: #f1f5f9; color: #334155; }
.chip.teal { background: #ccfbf1; color: #115e59; }
.chip.pink { background: #fce7f3; color: #9d174d; }
.diff { border-radius: 12px; padding: 10px 14px; margin-bottom: 8px; font-size: .92rem; border-left: 5px solid; line-height: 1.55; }
.diff.same { background: #f8fafc; border-color: #cbd5e1; color: #64748b; }
.diff.added { background: #ecfdf5; border-color: #10b981; }
.diff.removed { background: #fef2f2; border-color: #ef4444; }
.diff.changed { background: #fffbeb; border-color: #f59e0b; }
.badge { font-size: .68rem; font-weight: 800; letter-spacing: .07em; margin-right: 8px; padding: 2px 8px; border-radius: 6px; background: rgba(0,0,0,.07); }
ins { background: #bbf7d0; text-decoration: none; border-radius: 4px; padding: 0 3px; }
del { background: #fecaca; border-radius: 4px; padding: 0 3px; }
mark { border-radius: 4px; padding: 0 3px; }
mark.kw { background: #e0e7ff; color: #3730a3; }
mark.PERSON { background: #fce7f3; color: #9d174d; }
mark.ORGANIZATION { background: #dbeafe; color: #1e40af; }
mark.PLACE { background: #ccfbf1; color: #115e59; }
mark.DATE, mark.NUMBER, mark.MONEY { background: #fef3c7; color: #92400e; }
mark.EMAIL, mark.URL { background: #ede9fe; color: #5b21b6; }
mark.hit { background: #fde68a; color: #78350f; }
.answer { background: linear-gradient(120deg, #eef2ff, #f0f9ff); border: 1px solid #c7d2fe; border-radius: 18px; padding: 20px 24px; margin-bottom: 14px; }
.answer .short { font-size: 1.9rem; font-weight: 800; color: #4338ca; line-height: 1.2; }
.answer .sentence { font-size: 1.05rem; color: #1f2333; margin-top: 8px; }
.answer .meta { font-size: .82rem; color: #6b7280; margin-top: 10px; }
.bar { height: 8px; background: #e5e7eb; border-radius: 999px; overflow: hidden; margin-top: 6px; }
.bar > div { height: 100%; background: linear-gradient(90deg, #4f46e5, #0ea5e9); border-radius: 999px; }
.side-table { width: 100%; border-collapse: separate; border-spacing: 0 6px; font-size: .9rem; }
.side-table td { padding: 9px 12px; vertical-align: top; width: 50%; border-radius: 10px; }
.side-table tr.same td { background: #f8fafc; color: #64748b; }
.side-table tr.changed td { background: #fffbeb; }
.side-table tr.added td.right { background: #ecfdf5; }
.side-table tr.removed td.left { background: #fef2f2; }
.token { display: inline-block; text-align: center; margin: 4px 4px; padding: 6px 10px; border-radius: 12px; background: #fff; border: 1px solid #e5e7eb; box-shadow: 0 1px 4px rgba(0,0,0,.04); }
.token .word { font-weight: 700; font-size: .95rem; color: #1f2333; }
.token .tag { font-size: .68rem; font-weight: 700; color: #fff; border-radius: 6px; padding: 1px 6px; margin-top: 4px; display: inline-block; }
.footer { text-align: center; color: #9ca3af; font-size: .8rem; margin-top: 40px; }
.stTabs [role="tablist"] { gap: 6px; flex-wrap: wrap; }
.stTabs [role="tab"] { background: #eef0f8; border-radius: 10px; padding: 7px 16px; height: auto; border: none; cursor: pointer; transition: background .15s ease; }
.stTabs [role="tab"]:hover { background: #e0e7ff; }
.stTabs [role="tab"][aria-selected="true"] { background: #4f46e5; box-shadow: 0 4px 12px rgba(79,70,229,.3); }
.stTabs [role="tab"][aria-selected="true"] p { color: #fff !important; font-weight: 600; }
.stTabs .react-aria-SelectionIndicator { display: none; }
.stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] { display: none; }
</style>
"""

TAG_COLORS = {"N": "#4f46e5", "V": "#10b981", "J": "#f59e0b", "R": "#ec4899", "P": "#0ea5e9", "C": "#8b5cf6", "D": "#64748b", "I": "#14b8a6"}


def html(content):
    st.markdown(content, unsafe_allow_html=True)


def hero(tag, heading, text):
    html(f'<div class="hero"><span class="tag">{escape(tag)}</span><h1>{escape(heading)}</h1><p>{escape(text)}</p></div>')


def cards(items):
    blocks = []
    for index, item in enumerate(items):
        label, value, hint = item[0], item[1], item[2] if len(item) > 2 else ""
        color = item[3] if len(item) > 3 else COLORS[index % len(COLORS)]
        blocks.append(f'<div class="metric-card" style="--accent:{color}"><div class="label">{escape(str(label))}</div>'
                      f'<div class="value">{escape(str(value))}</div><div class="hint">{escape(str(hint))}</div></div>')
    html('<div class="card-grid">' + "".join(blocks) + "</div>")


def section(text):
    html(f'<div class="section-title">{escape(text)}</div>')


def chips(items, kind="info"):
    items = list(items)
    if not items:
        return '<span class="chip plain">none</span>'
    return "".join(f'<span class="chip {kind}">{escape(str(item))}</span>' for item in items)


def panel(title, body_html):
    html(f'<div class="panel"><h4>{escape(title)}</h4>{body_html}</div>')


def score_bar(value):
    width = max(0, min(100, value * 100))
    return f'<div class="bar"><div style="width:{width:.0f}%"></div></div>'


def show(figure, height=380):
    figure.update_layout(template="plotly_white", height=height, margin=dict(l=10, r=10, t=46, b=10), colorway=COLORS,
                         font=dict(family="Inter, sans-serif", size=12, color="#1f2333"), paper_bgcolor="rgba(0,0,0,0)",
                         plot_bgcolor="rgba(0,0,0,0)", title_font=dict(size=15))
    st.plotly_chart(figure, width="stretch", config={"displayModeBar": False})


def highlight(text, terms):
    if not terms:
        return escape(text).replace("\n", "<br>")
    lookup = {term.lower(): label for term, label in terms.items() if term.strip()}
    ordered = sorted(lookup, key=len, reverse=True)
    pattern = re.compile(r"(?<![\w])(" + "|".join(re.escape(term) for term in ordered) + r")(?![\w])", re.IGNORECASE)
    pieces = []
    last = 0
    for found in pattern.finditer(text):
        pieces.append(escape(text[last:found.start()]))
        pieces.append(f'<mark class="{lookup[found.group(0).lower()]}">{escape(found.group(0))}</mark>')
        last = found.end()
    pieces.append(escape(text[last:]))
    return "".join(pieces).replace("\n", "<br>")


def short(text, size=38):
    return text if len(text) <= size else text[:size - 3] + "..."


@st.cache_data(show_spinner=False)
def read_upload(name, data):
    return engine.read_bytes(name, data)


@st.cache_resource(show_spinner=False)
def build_corpus(items, skill_threshold):
    return engine.Corpus(dict(items), skill_threshold)


@st.cache_data(show_spinner=False)
def cached_roles(key, _corpus, version_similarity, topic_similarity):
    return engine.detect_roles(_corpus, version_similarity, topic_similarity)


@st.cache_data(show_spinner=False)
def cached_overview(key, _corpus):
    return engine.overview_table(_corpus)


@st.cache_data(show_spinner=False)
def cached_topics(key, _corpus):
    return engine.find_topics(_corpus)


@st.cache_data(show_spinner=False)
def cached_sentence_map(key, _corpus):
    items = [(name, sentence) for name in _corpus.names for sentence in _corpus.sentences[name]]
    return engine.sentence_map(_corpus.vectorizer, items)


@st.cache_data(show_spinner=False)
def cached_triples(key, _corpus, name):
    return engine.find_triples(_corpus.documents[name])


@st.cache_data(show_spinner=False)
def cached_match(key, _corpus, job_text, resume_name):
    return engine.match_resume(_corpus, job_text, _corpus.documents[resume_name])


def dashboard(corpus, roles, key):
    hero("MULTI DOCUMENT NLP SCANNER", "Understand many documents at once",
         "Resume matching, semantic version diffing, multi document summaries, question answering and a knowledge graph, "
         "all built on classic NLP: tokens, TF-IDF vectors, cosine similarity, POS tags and dynamic programming. No AI API keys.")
    overview = cached_overview(key, corpus)
    topic_words, topic_table = cached_topics(key, corpus)
    cards([
        ("Documents", len(corpus.names), "loaded and indexed"),
        ("Words", f"{int(overview['words'].sum()):,}", "across all files"),
        ("Sentences", f"{len(corpus.all_sentences):,}", "in the vector store"),
        ("Vocabulary", f"{len(corpus.vectorizer.word_model.vocabulary_):,}", "word features"),
        ("Topics", len(topic_words), "found with NMF"),
        ("Version groups", len(roles["version_groups"]), "auto detected"),
    ])

    section("What the scanner detected")
    groups_html = "".join(chips([" -> ".join(group)], "warn") for group in roles["version_groups"]) or chips([], "warn")
    topic_html = "".join(chips([", ".join(group)], "teal") for group in roles["summary_groups"])
    left, right = st.columns(2)
    with left:
        panel("Roles from file names", f"<b>Job description</b><br>{chips([roles['job_file']] if roles['job_file'] else [], 'info')}<br>"
                                       f"<b>Resumes</b><br>{chips(roles['resume_files'], 'pink')}<br>"
                                       f"<b>Reference summary</b><br>{chips([roles['reference_file']] if roles['reference_file'] else [], 'plain')}")
    with right:
        panel("Groups from content", f"<b>Versions of the same document</b><br>{groups_html}<br><b>Topic groups for summaries</b><br>{topic_html}")

    section("Document library")
    st.dataframe(overview, width="stretch", hide_index=True, column_config={
        "readability": st.column_config.ProgressColumn("readability", min_value=0, max_value=100, format="%.0f"),
        "sentiment": st.column_config.NumberColumn("sentiment", format="%.2f"),
    })

    left, right = st.columns(2)
    with left:
        figure = px.imshow(corpus.similarity, x=corpus.names, y=corpus.names, color_continuous_scale="Purples", zmin=0, zmax=1,
                           text_auto=".2f", title="How similar the documents are")
        figure.update_xaxes(tickangle=45)
        show(figure, 470)
    with right:
        points = cached_sentence_map(key, corpus)
        if not points.empty:
            points["text"] = points["sentence"].map(lambda value: short(value, 90))
            figure = px.scatter(points, x="x", y="y", color="document", hover_data={"text": True, "x": False, "y": False},
                                title="Sentence map: every sentence placed by meaning")
            figure.update_traces(marker=dict(size=10, opacity=0.8, line=dict(width=1, color="white")))
            figure.update_layout(legend=dict(font=dict(size=10)), xaxis_title=None, yaxis_title=None)
            show(figure, 470)

    left, right = st.columns([1, 1.4])
    with left:
        figure = px.pie(overview, names="type", hole=0.6, title="Detected document types")
        figure.update_traces(textinfo="value+percent")
        show(figure, 360)
    with right:
        figure = px.bar(overview.sort_values("words"), x="words", y="document", orientation="h", color="mood",
                        color_discrete_map={"Positive": "#10b981", "Neutral": "#94a3b8", "Negative": "#ef4444"},
                        title="Document length and mood")
        show(figure, 360)

    section("Topics found across the documents")
    columns = st.columns(min(3, len(topic_words)))
    for index, words in enumerate(topic_words):
        members = topic_table[topic_table["main topic"] == f"Topic {index + 1}"]["document"].tolist()
        with columns[index % len(columns)]:
            panel(f"Topic {index + 1}", chips(words, "info") + "<br><span style='font-size:.8rem;color:#6b7280'>Documents</span><br>" + chips(members, "plain"))


def explorer(corpus, key):
    hero("DOCUMENT EXPLORER", "Look inside one document", "Keywords, key phrases, writing style, readability, sentiment arc, entities and skills.")
    name = st.selectbox("Choose a document", corpus.names)
    text = corpus.documents[name]
    scores = engine.readability_scores(text)
    profile = engine.style_profile(text)
    mood_score, mood = engine.sentiment(text)
    doc_type, type_confidence, type_scores = engine.detect_document_type(text)
    language, language_confidence, language_scores = engine.detect_language(text)
    cards([
        ("Words", len(engine.alpha_words(text)), f"{len(corpus.sentences[name])} sentences"),
        ("Reading ease", scores["Flesch reading ease"], engine.reading_level(scores["Flesch reading ease"])),
        ("School grade", scores["Flesch-Kincaid grade"], "Flesch-Kincaid"),
        ("Mood", mood, f"score {mood_score}", "#10b981" if mood == "Positive" else "#ef4444" if mood == "Negative" else "#94a3b8"),
        ("Language", language, f"confidence {language_confidence}"),
        ("Type", doc_type, f"confidence {type_confidence}"),
    ])
    tabs = st.tabs(["Overview", "Keywords", "Writing style", "Sentiment", "Entities and skills", "Full text"])

    with tabs[0]:
        summary, trace = engine.summarize(corpus, [name], 3)
        panel("Short summary", escape(summary or "This document is too short to summarise."))
        left, right = st.columns(2)
        with left:
            panel("Top keywords (TF-IDF)", chips(corpus.top_keywords(name, 10), "info"))
        with right:
            panel("Key phrases (RAKE)", chips([phrase for phrase, score in engine.rake_keyphrases(text, 10)], "teal"))
        figure = px.bar(pd.DataFrame(type_scores, columns=["type", "score"]), x="score", y="type", orientation="h",
                        title="Why this document type was chosen")
        figure.update_yaxes(categoryorder="total ascending")
        show(figure, 330)

    with tabs[1]:
        weights = pd.DataFrame(corpus.keyword_weights(name, 30), columns=["keyword", "weight"])
        left, right = st.columns([1.3, 1])
        with left:
            if not weights.empty:
                figure = px.treemap(weights, path=["keyword"], values="weight", color="weight", color_continuous_scale="Purples",
                                    title="Keyword map (bigger means more important)")
                figure.update_traces(textfont=dict(size=15))
                show(figure, 430)
        with right:
            figure = px.bar(weights.head(12).sort_values("weight"), x="weight", y="keyword", orientation="h", title="Top TF-IDF weights")
            show(figure, 430)
        left, right = st.columns(2)
        with left:
            st.markdown("**Key phrases with RAKE scores**")
            st.dataframe(pd.DataFrame(engine.rake_keyphrases(text, 12), columns=["phrase", "score"]), width="stretch", hide_index=True)
        with right:
            st.markdown("**Strong word pairs (collocations)**")
            st.dataframe(pd.DataFrame(engine.word_pairs(text, 12), columns=["pair", "likelihood score", "count"]), width="stretch", hide_index=True)

    with tabs[2]:
        left, right = st.columns(2)
        with left:
            pos = pd.DataFrame(list(profile["pos counts"].items()), columns=["part of speech", "count"])
            figure = px.pie(pos, names="part of speech", values="count", hole=0.55, title="Parts of speech")
            show(figure, 380)
        with right:
            score_frame = pd.DataFrame(list(scores.items()), columns=["formula", "score"])
            figure = px.bar(score_frame, x="formula", y="score", color="formula", text="score", title="Four readability formulas")
            figure.update_layout(showlegend=False)
            show(figure, 380)
        cards([
            ("Lexical diversity", profile["lexical diversity"], "unique words / words"),
            ("Average word length", profile["average word length"], "letters"),
            ("Long words", f"{profile['long word ratio'] * 100:.0f}%", "7 letters or more"),
            ("Gunning fog", scores["Gunning fog"], "years of school needed"),
        ])
        zipf = engine.zipf_table(text)
        left, right = st.columns(2)
        with left:
            if not zipf.empty:
                figure = px.scatter(zipf, x="rank", y="count", hover_data=["word"], log_x=True, log_y=True, title="Zipf's law: word rank vs count")
                figure.update_traces(marker=dict(size=9, color="#7c3aed", opacity=0.7))
                show(figure, 360)
        with right:
            figure = px.bar(zipf.head(15), x="word", y="count", title="Most used words", color="count", color_continuous_scale="Blues")
            show(figure, 360)

    with tabs[3]:
        arc = engine.sentiment_arc(text)
        if not arc.empty:
            arc["text"] = arc["sentence"].map(lambda value: short(value, 100))
            figure = go.Figure()
            figure.add_hline(y=0, line_dash="dot", line_color="#94a3b8")
            figure.add_trace(go.Scatter(x=arc["position"], y=arc["score"], mode="lines+markers", line=dict(color="#c7d2fe", width=3, shape="spline"),
                                        marker=dict(size=12, color=arc["score"], colorscale="RdYlGn", cmin=-1, cmax=1, line=dict(width=1, color="white")),
                                        text=arc["text"], hovertemplate="Sentence %{x}<br>%{text}<br>Score %{y}<extra></extra>"))
            figure.update_layout(title="Sentiment arc through the document", xaxis_title="sentence number", yaxis_title="VADER score", yaxis_range=[-1.05, 1.05])
            show(figure, 400)
            left, right = st.columns(2)
            with left:
                best = arc.sort_values("score", ascending=False).head(3)
                panel("Most positive sentences", "".join(f'<div class="diff added">{escape(row.sentence)} <b>({row.score})</b></div>' for row in best.itertuples()))
            with right:
                worst = arc.sort_values("score").head(3)
                panel("Most negative sentences", "".join(f'<div class="diff removed">{escape(row.sentence)} <b>({row.score})</b></div>' for row in worst.itertuples()))

    with tabs[4]:
        entities = corpus.entities(name)
        kinds = {"PERSON": "pink", "ORGANIZATION": "info", "PLACE": "teal", "DATE": "warn", "NUMBER": "warn", "MONEY": "warn", "EMAIL": "plain", "URL": "plain"}
        body = "".join(f"<b>{label.title()}</b><br>{chips([item for item, count in counter.most_common(12)], kinds[label])}<br>"
                       for label, counter in entities.items() if counter)
        left, right = st.columns(2)
        with left:
            panel("Named entities and facts", body or "No entities found.")
        with right:
            skills = corpus.skills[name]
            panel("Skills and competences", chips(skills.keys(), "good") + "<br><br>" +
                  "".join(f"<div style='font-size:.85rem'><b>{escape(skill)}</b> found as <i>{escape(str(evidence))}</i></div>" for skill, evidence in skills.items()))
        terms = {item: label for label, counter in entities.items() for item in counter}
        panel("Text with entities highlighted", highlight(text, terms))

    with tabs[5]:
        terms = {keyword: "kw" for keyword in corpus.top_keywords(name, 12)}
        panel("Full text with the top keywords highlighted", highlight(text, terms))
        st.download_button("Download the extracted text", text, file_name=name.rsplit(".", 1)[0] + ".txt")


def diff_html(result, show_same=True):
    blocks = []
    for label, old_sentence, new_sentence, value in result["steps"]:
        if label == "SAME" and show_same:
            blocks.append(f'<div class="diff same"><span class="badge">SAME {value:.2f}</span>{escape(new_sentence)}</div>')
        elif label == "ADDED":
            blocks.append(f'<div class="diff added"><span class="badge">ADDED</span>{escape(new_sentence)}</div>')
        elif label == "REMOVED":
            blocks.append(f'<div class="diff removed"><span class="badge">REMOVED</span>{escape(old_sentence)}</div>')
        elif label == "CHANGED":
            blocks.append(f'<div class="diff changed"><span class="badge">CHANGED {value:.2f}</span>{engine.word_diff_html(old_sentence, new_sentence)}</div>')
    return "".join(blocks)


def side_by_side_html(result):
    rows = []
    for label, old_sentence, new_sentence, value in result["steps"]:
        css = label.lower()
        rows.append(f'<tr class="{css}"><td class="left">{escape(old_sentence)}</td><td class="right">{escape(new_sentence)}</td></tr>')
    return '<table class="side-table"><tr><th>First document</th><th>Second document</th></tr>' + "".join(rows) + "</table>"


def alignment_figure(corpus, old_text, new_text):
    old_sentences = [engine.strip_numbering(s) for s in engine.split_sentences(old_text)]
    new_sentences = [engine.strip_numbering(s) for s in engine.split_sentences(new_text)]
    steps, matrix = engine.needleman_wunsch(old_sentences, new_sentences, corpus.vectorizer)
    if matrix.shape == (1, 1):
        return None
    path_x, path_y = [0], [0]
    i = j = 0
    for label, old_sentence, new_sentence, value in steps:
        if label in ("SAME", "CHANGED"):
            i, j = i + 1, j + 1
        elif label == "ADDED":
            j += 1
        else:
            i += 1
        path_x.append(j)
        path_y.append(i)
    x_labels = ["(gap)"] + [f"{n + 1}. {short(s, 22)}" for n, s in enumerate(new_sentences)]
    y_labels = ["(gap)"] + [f"{n + 1}. {short(s, 22)}" for n, s in enumerate(old_sentences)]
    figure = go.Figure(go.Heatmap(z=matrix, x=list(range(len(x_labels))), y=list(range(len(y_labels))), colorscale="Purples",
                                  text=matrix.round(1), texttemplate="%{text}", textfont=dict(size=9), showscale=True))
    figure.add_trace(go.Scatter(x=path_x, y=path_y, mode="lines+markers", line=dict(color="#f59e0b", width=4),
                                marker=dict(size=8, color="#f59e0b"), name="best alignment path"))
    figure.update_xaxes(tickvals=list(range(len(x_labels))), ticktext=x_labels, tickangle=45, side="top")
    figure.update_yaxes(tickvals=list(range(len(y_labels))), ticktext=y_labels, autorange="reversed")
    figure.update_layout(title="Needleman-Wunsch score matrix and traceback path", showlegend=False)
    return figure


def compare_page(corpus, roles):
    hero("SEMANTIC DOCUMENT DIFFING", "See what really changed",
         "Sentences are turned into vectors and aligned with the Needleman-Wunsch algorithm, so rewording is not counted as a change but new facts and numbers are.")
    mode = st.segmented_control("What do you want to compare?", ["Two documents", "Two pasted texts"], default="Two documents")
    if mode == "Two pasted texts":
        left, right = st.columns(2)
        old_text = left.text_area("First text", "Every employee gets 12 days of leave.\nRequests go to the manager one week before.", height=180)
        new_text = right.text_area("Second text", "Every employee gets 15 days of leave.\nRequests go to the manager one week before.\nStaff may work from home twice a month.", height=180)
        if not old_text.strip() or not new_text.strip():
            st.info("Type some text in both boxes.")
            return
        result = engine.compare_texts(corpus, old_text, new_text)
        old_name, new_name = "first text", "second text"
    else:
        default_old, default_new = (roles["version_groups"][0][0], roles["version_groups"][0][1]) if roles["version_groups"] else (corpus.names[0], corpus.names[-1])
        left, right = st.columns(2)
        old_name = left.selectbox("First (older) document", corpus.names, index=corpus.names.index(default_old))
        new_name = right.selectbox("Second (newer) document", corpus.names, index=corpus.names.index(default_new))
        old_text, new_text = corpus.documents[old_name], corpus.documents[new_name]
        result = engine.compare_documents(corpus, old_name, new_name)

    counts = result["counts"]
    real_changes = counts["CHANGED"] + counts["ADDED"] + counts["REMOVED"]
    cards([
        ("Similarity", f"{result['similarity']:.2f}", "cosine of document vectors"),
        ("Same", counts["SAME"], "meaning kept", "#94a3b8"),
        ("Changed", counts["CHANGED"], "edited sentences", "#f59e0b"),
        ("Added", counts["ADDED"], "new sentences", "#10b981"),
        ("Removed", counts["REMOVED"], "dropped sentences", "#ef4444"),
        ("Line diff noise", result["lexical lines flagged"], f"vs {real_changes} real changes", "#8b5cf6"),
    ])
    left, middle, right = st.columns([1, 1, 1.2])
    with left:
        figure = go.Figure(go.Indicator(mode="gauge+number", value=result["similarity"] * 100, number=dict(suffix="%"),
                                        gauge=dict(axis=dict(range=[0, 100]), bar=dict(color="#4f46e5"),
                                                   steps=[dict(range=[0, 40], color="#fee2e2"), dict(range=[40, 70], color="#fef3c7"), dict(range=[70, 100], color="#dcfce7")])))
        figure.update_layout(title="Overall similarity")
        show(figure, 260)
    with middle:
        figure = px.pie(names=list(counts.keys()), values=list(counts.values()), hole=0.6, title="Sentence outcomes", color=list(counts.keys()),
                        color_discrete_map={"SAME": "#cbd5e1", "CHANGED": "#f59e0b", "ADDED": "#10b981", "REMOVED": "#ef4444"})
        show(figure, 260)
    with right:
        panel("Semantic relation", f"<div style='font-size:1.35rem;font-weight:800;color:#4338ca'>{escape(result['relation'])}</div>"
                                   f"<div style='color:#6b7280'>{escape(result['relation meaning'])}</div><br>"
                                   f"<b>Alignment score</b> {result['alignment score']}<br>"
                                   f"<span style='font-size:.85rem;color:#6b7280'>Equivalence = same facts, Inclusion = one fully inside the other, Overlap = both have unique parts.</span>")

    tabs = st.tabs(["Change list", "Side by side", "Keywords and numbers", "Copy check", "Alignment matrix", "Version timeline"])
    with tabs[0]:
        show_same = st.toggle("Show unchanged sentences", value=True)
        html(diff_html(result, show_same))
    with tabs[1]:
        html(side_by_side_html(result))
    with tabs[2]:
        left, right = st.columns(2)
        with left:
            panel("Keywords only in the first", chips(result["keywords only in old"], "bad"))
            panel("Numbers removed", chips(result["numbers removed"], "bad"))
            panel("Skills removed", chips(result["skills removed"], "bad"))
        with right:
            panel("Keywords only in the second", chips(result["keywords only in new"], "good"))
            panel("Numbers added", chips(result["numbers added"], "good"))
            panel("Skills added", chips(result["skills added"], "good"))
        panel("Shared keywords", chips(result["shared keywords"], "info"))
    with tabs[3]:
        check = engine.copy_check(old_text, new_text)
        cards([
            ("Jaccard overlap", f"{check['jaccard'] * 100:.0f}%", "shared 4 word phrases"),
            ("First found in second", f"{check['A found in B'] * 100:.0f}%", "containment"),
            ("Second found in first", f"{check['B found in A'] * 100:.0f}%", "containment"),
        ])
        panel("Shared exact phrases", chips(check["shared phrases"], "warn"))
    with tabs[4]:
        figure = alignment_figure(corpus, old_text, new_text)
        if figure is None:
            st.info("One of the documents has no sentences.")
        else:
            st.caption("Each cell is the best alignment score so far. The orange line is the traceback path: diagonal = matched, right = added, down = removed.")
            show(figure, max(420, 34 * figure.data[0].z.shape[0] + 160))
    with tabs[5]:
        group = next((group for group in roles["version_groups"] if old_name in group and new_name in group), None)
        if not group:
            st.info("These two files are not part of a detected version group. Name files like report_v1 and report_v2 to see a timeline.")
        else:
            rows = []
            for first, second in zip(group, group[1:]):
                step = engine.compare_documents(corpus, first, second)
                rows.append({"step": f"{short(first, 18)} -> {short(second, 18)}", **step["counts"], "similarity": step["similarity"]})
            timeline = pd.DataFrame(rows)
            figure = go.Figure()
            for label, color in [("CHANGED", "#f59e0b"), ("ADDED", "#10b981"), ("REMOVED", "#ef4444")]:
                figure.add_trace(go.Bar(x=timeline["step"], y=timeline[label], name=label, marker_color=color))
            figure.add_trace(go.Scatter(x=timeline["step"], y=timeline["similarity"], name="similarity", yaxis="y2", mode="lines+markers",
                                        line=dict(color="#4f46e5", width=3)))
            figure.update_layout(barmode="stack", title="How the document evolved", yaxis2=dict(overlaying="y", side="right", range=[0, 1], title="similarity"))
            show(figure, 380)


def resume_page(corpus, roles, key):
    hero("COMPETENCE BASED MATCHING", "Rank candidates by real skills",
         "Skills are found with POS tags, phrase lookup and vector similarity against a skill taxonomy. Personal details are removed before scoring.")
    default_job = roles["job_file"] or corpus.names[0]
    left, right = st.columns([1, 2])
    job_name = left.selectbox("Job description", corpus.names, index=corpus.names.index(default_job))
    candidates = [name for name in corpus.names if name != job_name]
    default_resumes = [name for name in roles["resume_files"] if name in candidates] or candidates[:3]
    resume_names = right.multiselect("Resumes to rank", candidates, default=default_resumes)
    with st.expander("Or paste a different job description"):
        pasted_job = st.text_area("Job description text", "", height=140)
    job_text = pasted_job.strip() or corpus.documents[job_name]
    if not resume_names:
        st.info("Choose at least one resume.")
        return
    results = {name: cached_match(key, corpus, job_text, name) for name in resume_names}
    ordered = sorted(results, key=lambda name: results[name]["final_score"], reverse=True)
    best = ordered[0]
    job_skills = results[best]["job_skills"]
    cards([
        ("Candidates", len(ordered), "ranked"),
        ("Best match", short(best, 20), f"score {results[best]['final_score']:.2f}", "#10b981"),
        ("Skills required", len(job_skills), "from the job text"),
        ("Average score", f"{sum(r['final_score'] for r in results.values()) / len(results):.2f}", "all candidates"),
    ])
    panel("Skills the job needs", chips(job_skills, "info"))

    left, right = st.columns([1.3, 1])
    with left:
        rows = []
        for name in ordered:
            result = results[name]
            if job_skills:
                rows += [{"resume": name, "part": "skills x 0.60", "points": 0.6 * result["skill_score"]},
                         {"resume": name, "part": "requirements x 0.25", "points": 0.25 * result["coverage"]},
                         {"resume": name, "part": "text x 0.15", "points": 0.15 * result["text_score"]}]
            else:
                rows += [{"resume": name, "part": "requirements x 0.60", "points": 0.6 * result["coverage"]},
                         {"resume": name, "part": "text x 0.40", "points": 0.4 * result["text_score"]}]
        figure = px.bar(pd.DataFrame(rows), x="points", y="resume", color="part", orientation="h", barmode="stack", title="Ranking and how each score is built")
        figure.update_layout(legend=dict(orientation="h", y=-0.15), yaxis_title=None)
        figure.update_yaxes(categoryorder="array", categoryarray=list(reversed(ordered)))
        show(figure, 360)
    with right:
        figure = go.Figure()
        axes = ["Skill match", "Requirement coverage", "Text similarity", "Skill breadth"]
        widest = max(len(results[name]["evidence"]) for name in ordered) or 1
        for name in ordered:
            result = results[name]
            values = [result["skill_score"], result["coverage"], result["text_score"], len(result["evidence"]) / widest]
            figure.add_trace(go.Scatterpolar(r=values + values[:1], theta=axes + axes[:1], fill="toself", name=short(name, 22), opacity=0.55))
        figure.update_layout(title="Candidate profile", polar=dict(radialaxis=dict(range=[0, 1], showticklabels=False)))
        show(figure, 360)

    if job_skills:
        matrix = pd.DataFrame([[1 if skill in results[name]["matched"] else 0 for skill in job_skills] for name in ordered], index=ordered, columns=job_skills)
        figure = px.imshow(matrix, color_continuous_scale=[[0, "#fee2e2"], [1, "#10b981"]], zmin=0, zmax=1, title="Skill matrix (green = has the skill)", aspect="auto")
        figure.update_coloraxes(showscale=False)
        figure.update_xaxes(tickangle=35)
        show(figure, 120 + 46 * len(ordered))

    section("Candidate details")
    for rank, name in enumerate(ordered, 1):
        result = results[name]
        with st.expander(f"#{rank}  {name}   |   score {result['final_score']:.2f}", expanded=rank == 1):
            left, right = st.columns(2)
            with left:
                panel("Matched skills", chips(result["matched"], "good"))
                panel("Missing skills", chips(result["missing"], "bad"))
            with right:
                panel("Extra skills", chips(result["extra"], "info"))
                notes = result["rejected"]
                panel("False positives blocked by the POS filter", chips(notes, "warn") if notes else "None in this resume.")
            evidence = pd.DataFrame(list(result["evidence"].items()), columns=["skill", "found as"])
            st.dataframe(evidence, width="stretch", hide_index=True)
            if result["coverage_rows"]:
                coverage = pd.DataFrame(result["coverage_rows"])
                st.dataframe(coverage, width="stretch", hide_index=True, column_config={
                    "score": st.column_config.ProgressColumn("score", min_value=0, max_value=1, format="%.2f")})
            with st.popover("What the matcher actually read"):
                st.text(engine.remove_personal_details(corpus.documents[name]).strip())

    section("Fairness check")
    st.caption("Each resume is scored again with a different name and swapped gender words. A fair matcher gives the same score.")
    if st.button("Run the fairness check"):
        with st.spinner("Scoring counterfactual resumes"):
            table = engine.fairness_check(corpus, job_name, resume_names)
        passed = bool(table["fair"].all())
        html(chips(["All scores stayed the same"], "good") if passed else chips(["Some scores changed"], "bad"))
        st.dataframe(table, width="stretch", hide_index=True)


def summarizer_page(corpus, roles):
    hero("MULTI DOCUMENT SUMMARY", "Many documents, one short story",
         "TextRank on a sentence similarity graph picks the evidence, redundancy is removed, then simple rewrite rules join and shorten it. Every sentence is traced to its source.")
    default_group = roles["summary_groups"][0] if roles["summary_groups"] else corpus.names[:1]
    left, right = st.columns([2.2, 1])
    chosen = left.multiselect("Documents to summarise", corpus.names, default=default_group)
    size = right.slider("Summary length (sentences)", 1, 10, 4)
    if not chosen:
        st.info("Choose at least one document.")
        return
    summary, trace = engine.summarize(corpus, chosen, size)
    source_words = sum(len(engine.alpha_words(corpus.documents[name])) for name in chosen)
    summary_words = len(engine.alpha_words(summary))
    cards([
        ("Source words", f"{source_words:,}", f"{len(chosen)} documents"),
        ("Summary words", summary_words, f"{len(trace)} evidence sentences"),
        ("Compression", f"{(1 - summary_words / max(source_words, 1)) * 100:.0f}%", "shorter than the source"),
        ("Sources used", len({item['source'] for item in trace}), "documents quoted"),
    ])
    html(f'<div class="answer"><div style="font-size:.78rem;font-weight:800;letter-spacing:.08em;color:#6366f1">SUMMARY</div>'
         f'<div class="sentence" style="line-height:1.9">{escape(summary or "Nothing to summarise.")}</div></div>')
    if trace:
        frame = pd.DataFrame(trace)
        left, right = st.columns([1.4, 1])
        with left:
            st.markdown("**Where every sentence came from**")
            st.dataframe(frame, width="stretch", hide_index=True, column_config={
                "score": st.column_config.ProgressColumn("importance", min_value=0, max_value=1, format="%.2f")})
        with right:
            figure = px.pie(frame, names="source", hole=0.55, title="Share of each source")
            show(figure, 300)

    section("Check the quality with ROUGE")
    options = ["(paste my own)"] + corpus.names
    default_reference = options.index(roles["reference_file"]) if roles["reference_file"] in options else 0
    reference_name = st.selectbox("Reference summary", options, index=default_reference)
    reference = st.text_area("Reference text", "", height=110) if reference_name == "(paste my own)" else corpus.documents[reference_name]
    if reference.strip() and summary:
        evaluation = engine.evaluate_summary(corpus, summary, reference).reset_index().rename(columns={"index": "metric"})
        melted = evaluation.melt(id_vars="metric", var_name="measure", value_name="value")
        figure = px.bar(melted, x="metric", y="value", color="measure", barmode="group", title="ROUGE and vector similarity", text="value")
        figure.update_layout(yaxis_range=[0, 1])
        show(figure, 360)

    with st.expander("Short summary of every single document"):
        for name in corpus.names:
            single, single_trace = engine.summarize(corpus, [name], 2)
            panel(name, escape(single or "Too short to summarise."))


def ask_page(corpus):
    hero("QUESTION ANSWERING", "Ask your documents anything",
         "The question becomes a vector, the closest sentences are found with cosine similarity, and the question type (how many, when, who, where) pulls out a short answer.")
    st.session_state.setdefault("history", [])
    keywords = []
    for name in corpus.names:
        for keyword in corpus.top_keywords(name, 3):
            if keyword not in keywords and " " not in keyword:
                keywords.append(keyword)
                break
    examples = [f"What is said about {keyword}?" for keyword in keywords[:4]] + ["How many days, people or items are mentioned?", "Where does this take place?"]
    picked = st.pills("Try an example", examples, selection_mode="single")
    question = st.text_input("Your question", value=picked or "", placeholder="Type a question about your documents")
    left, right = st.columns([2, 1])
    only = left.multiselect("Search only in", corpus.names, default=[])
    top_k = right.slider("Number of results", 1, 10, 5)
    if not question.strip():
        st.info("Type a question or pick an example.")
        return
    answer = engine.answer_question(question, corpus.store, top_k=top_k, only_from=only or None)
    if question not in st.session_state["history"]:
        st.session_state["history"] = ([question] + st.session_state["history"])[:8]
    if not answer["answer sentence"]:
        st.warning("No matching sentence was found.")
        return
    terms = {word: "hit" for word in set(engine.word_tokenize(question.lower())) if word.isalpha() and word not in engine.stop_words}
    short_html = f'<div class="short">{escape(answer["short answer"])}</div>' if answer["short answer"] else ""
    html(f'<div class="answer">{chips([answer["question type"]], "info")}{short_html}'
         f'<div class="sentence">{highlight(answer["answer sentence"], terms)}</div>'
         f'<div class="meta">Source: <b>{escape(answer["source"])}</b> &nbsp; Match score {answer["score"]:.2f}</div>{score_bar(answer["score"])}</div>')
    if answer["other results"]:
        section("Other close sentences")
        for item in answer["other results"]:
            html(f'<div class="panel"><span class="chip plain">{escape(item["source"])}</span> {highlight(item["text"], terms)}{score_bar(item["score"])}</div>')
    if len(st.session_state["history"]) > 1:
        section("Recent questions")
        html(chips(st.session_state["history"], "plain"))


def graph_page(corpus, roles, key):
    hero("KNOWLEDGE GRAPH", "Who does what to whom",
         "POS tag patterns find noun phrase, verb phrase, noun phrase triples. Each triple becomes a link between two ideas.")
    default_docs = roles["summary_groups"][0] if roles["summary_groups"] else corpus.names
    chosen = st.multiselect("Documents to use", corpus.names, default=default_docs)
    if not chosen:
        st.info("Choose at least one document.")
        return
    triples = pd.concat([cached_triples(key, corpus, name).assign(document=name) for name in chosen], ignore_index=True)
    if triples.empty:
        st.warning("No subject, verb, object patterns were found in these documents.")
        return
    graph = engine.build_graph(triples)
    central = sorted(graph.degree, key=lambda item: item[1], reverse=True)
    cards([("Triples", len(triples), "subject, verb, object"), ("Ideas", graph.number_of_nodes(), "graph nodes"),
           ("Links", graph.number_of_edges(), "graph edges"), ("Most connected", short(central[0][0], 20), f"{central[0][1]} links")])
    layout = nx.spring_layout(graph, seed=7, k=1.4 / max(graph.number_of_nodes() ** 0.5, 1))
    edge_x, edge_y, middle_x, middle_y, middle_text = [], [], [], [], []
    for start, end, data in graph.edges(data=True):
        x0, y0 = layout[start]
        x1, y1 = layout[end]
        edge_x += [x0, x1, None]
        edge_y += [y0, y1, None]
        middle_x.append((x0 + x1) / 2)
        middle_y.append((y0 + y1) / 2)
        middle_text.append(f"{start} <b>{data['label']}</b> {end}")
    degrees = dict(graph.degree)
    figure = go.Figure()
    figure.add_trace(go.Scatter(x=edge_x, y=edge_y, mode="lines", line=dict(color="#c7d2fe", width=1.6), hoverinfo="skip"))
    figure.add_trace(go.Scatter(x=middle_x, y=middle_y, mode="markers", marker=dict(size=7, color="#f59e0b", symbol="diamond"),
                                text=middle_text, hovertemplate="%{text}<extra></extra>"))
    figure.add_trace(go.Scatter(x=[layout[node][0] for node in graph.nodes], y=[layout[node][1] for node in graph.nodes], mode="markers+text",
                                text=list(graph.nodes), textposition="top center", textfont=dict(size=10),
                                marker=dict(size=[12 + 6 * degrees[node] for node in graph.nodes], color=[degrees[node] for node in graph.nodes],
                                            colorscale="Purples", cmin=0, line=dict(width=2, color="white")),
                                hovertemplate="%{text}<extra></extra>"))
    figure.update_layout(title="Knowledge graph (hover the orange diamonds to read the relation)", showlegend=False,
                         xaxis=dict(visible=False), yaxis=dict(visible=False))
    show(figure, 620)
    section("All triples")
    st.dataframe(triples[["document", "subject", "relation", "object", "sentence"]], width="stretch", hide_index=True)


def playground_page(corpus):
    hero("NLP PLAYGROUND", "Try classic NLP on your own text", "Tokenizing, stemming, lemmatizing, POS tagging, entities, WordNet, language detection, privacy redaction and skill finding.")
    tabs = st.tabs(["Pipeline", "Word meanings", "Language detector", "Privacy redaction", "Skill finder"])
    with tabs[0]:
        sentence = st.text_input("Sentence", "Sara Khan was building better dashboards for Google in London last year.")
        if sentence.strip():
            table = engine.nlp_pipeline(sentence)
            tokens = []
            for row in table.to_dict("records"):
                tag = row["POS tag"]
                color = TAG_COLORS.get(tag[0], "#94a3b8") if tag[0].isalpha() else "#94a3b8"
                tokens.append(f'<div class="token"><div class="word">{escape(row["token"])}</div><div class="tag" style="background:{color}">{escape(tag)}</div></div>')
            panel("POS tags", "".join(tokens))
            st.dataframe(table, width="stretch", hide_index=True)
    with tabs[1]:
        word = st.text_input("Word", "growth")
        if word.strip():
            meanings = engine.word_meaning(word, 6)
            if meanings.empty:
                st.warning("WordNet does not know this word.")
            else:
                synonyms = sorted({item.strip() for value in meanings["synonyms"] for item in value.split(",") if item.strip()})
                opposites = sorted({item.strip() for value in meanings["opposites"] for item in value.split(",") if item.strip()})
                left, right = st.columns(2)
                with left:
                    panel("Synonyms", chips(synonyms, "good"))
                with right:
                    panel("Opposites", chips(opposites, "bad"))
                st.dataframe(meanings, width="stretch", hide_index=True)
    with tabs[2]:
        sample = st.text_area("Text in any language", "Le chat est sur la table et il dort avec le chien pendant que nous mangeons.", height=110)
        if sample.strip():
            language, confidence, scores = engine.detect_language(sample)
            cards([("Detected language", language, f"confidence {confidence}")])
            figure = px.bar(pd.DataFrame(scores, columns=["language", "stopwords found"]), x="language", y="stopwords found", color="language",
                            title="Stopword overlap with each language")
            figure.update_layout(showlegend=False)
            show(figure, 320)
    with tabs[3]:
        source = st.selectbox("Document to redact", ["(paste my own)"] + corpus.names, index=1 + next((i for i, n in enumerate(corpus.names) if "resume" in n.lower()), 0))
        original = st.text_area("Text", "Name: John Smith\nEmail: john@mail.com\nPhone: +91 98765 43210") if source == "(paste my own)" else corpus.documents[source]
        redacted, counts = engine.redact_text(original)
        html(chips([f"{label}: {count}" for label, count in counts.items()], "warn"))
        left, right = st.columns(2)
        with left:
            panel("Original", escape(original).replace("\n", "<br>"))
        with right:
            panel("Redacted", highlight(redacted, {f"[{label}]": "PERSON" for label in ["PERSON", "EMAIL", "PHONE", "URL"]}))
        st.download_button("Download redacted text", redacted, file_name="redacted.txt")
    with tabs[4]:
        text = st.text_area("Any text with skills", "I build REST APIs in Python, use Docker and AWS, and I love frontend scripting. We hand-polish every screen.", height=110)
        if text.strip():
            found, rejected = corpus.skill_finder.extract(text)
            panel("Skills found", chips(found.keys(), "good"))
            if rejected:
                panel("Rejected by the POS filter", chips(rejected, "warn"))
            st.dataframe(pd.DataFrame(list(found.items()), columns=["skill", "found as"]), width="stretch", hide_index=True)


def quality_page(corpus, roles):
    hero("QUALITY, DRIFT AND COPIES", "Keep the system honest", "Automatic tests, speed checks, vocabulary drift and copied content between documents.")
    drift_table, unusual_table = engine.drift_report(corpus, roles["version_groups"])
    left, right = st.columns(2)
    with left:
        section("Drift between versions")
        if drift_table.empty:
            st.info("No version groups were found.")
        else:
            st.dataframe(drift_table, width="stretch", hide_index=True)
            if drift_table["drift"].any():
                html(chips(["Drift found: the vectorizer should be retrained"], "bad"))
            else:
                html(chips(["No drift: the current model is fine"], "good"))
    with right:
        section("How unusual each document is")
        figure = px.bar(unusual_table.sort_values("distance from the rest"), x="distance from the rest", y="document", orientation="h",
                        color="new word ratio", color_continuous_scale="Sunset", title="Jensen-Shannon distance from all other documents")
        show(figure, 360)
    section("Copied or shared sentences between different documents")
    threshold = st.slider("Similarity needed to count as a copy", 0.5, 1.0, 0.8, 0.05)
    shared = engine.shared_sentences(corpus, roles["version_groups"], threshold)
    if shared.empty:
        html(chips(["No copied sentences found"], "good"))
    else:
        st.dataframe(shared, width="stretch", hide_index=True)
    section("Automatic tests and speed")
    if st.button("Run all tests and the speed check"):
        with st.spinner("Running tests"):
            tests = engine.run_self_tests(corpus)
            bench = engine.run_benchmark(corpus, roles)
        passed = int((tests["result"] == "PASSED").sum())
        cards([("Tests passed", f"{passed} / {len(tests)}", "unit checks", "#10b981" if passed == len(tests) else "#ef4444"),
               ("Slowest task", bench.sort_values("average ms").iloc[-1]["task"], f"{bench['average ms'].max():.0f} ms")])
        left, right = st.columns(2)
        with left:
            st.dataframe(tests, width="stretch", hide_index=True)
        with right:
            figure = px.bar(bench, x="task", y="average ms", color="task", title="Average time per task")
            figure.update_layout(showlegend=False)
            show(figure, 330)


def report_page(corpus, roles, key):
    hero("REPORT AND EXPORT", "Take the results with you", "A ReportLab PDF with tables, a heatmap and colour coded changes, plus CSV and JSON exports.")
    left, middle, right = st.columns(3)
    with left:
        panel("PDF report", "Overview, heatmap, entities, skills, resume ranking, fairness, version changes, summaries, drift and tests.")
        if st.button("Build the PDF report", type="primary"):
            with st.spinner("Building the report"):
                st.session_state["report"] = engine.build_report(corpus, roles)
        if st.session_state.get("report"):
            st.download_button("Download PDF report", st.session_state["report"], file_name="nlp_scanner_report.pdf", mime="application/pdf")
    overview = cached_overview(key, corpus)
    with middle:
        panel("Document table", "One row per document with type, language, readability, mood and keywords.")
        st.download_button("Download CSV", overview.to_csv(index=False), file_name="document_overview.csv", mime="text/csv")
    with right:
        panel("Full analysis as JSON", "Roles, overview, keywords, key phrases, skills and summaries for every document.")
        data = {
            "roles": roles,
            "documents": overview.to_dict(orient="records"),
            "details": {name: {"keywords": corpus.top_keywords(name, 10), "key phrases": [p for p, s in engine.rake_keyphrases(corpus.documents[name], 8)],
                               "skills": list(corpus.skills[name].keys()), "summary": engine.summarize(corpus, [name], 2)[0]} for name in corpus.names},
        }
        st.download_button("Download JSON", json.dumps(data, indent=2, default=str), file_name="analysis.json", mime="application/json")


def welcome():
    hero("WELCOME", "Upload your documents to begin",
         "Drop PDF, Word, text, Markdown, CSV or HTML files into the sidebar, or paste text as a document. Everything runs on your computer with classic NLP.")
    cards([
        ("Step 1", "Upload", "one or many files", "#4f46e5"),
        ("Step 2", "Pick a page", "from the sidebar", "#0ea5e9"),
        ("Step 3", "Explore", "charts, diffs and answers", "#10b981"),
        ("Step 4", "Export", "PDF, CSV or JSON", "#f59e0b"),
    ])
    section("What each page needs")
    guide = pd.DataFrame([
        ("Dashboard, Document Explorer, Summarizer, Ask Questions, Knowledge Graph", "Any documents", "works with one file or many"),
        ("Compare Documents", "Two versions of a document", "for example policy_v1.pdf and policy_v2.pdf"),
        ("Resume Matcher", "One job description and some resumes", "for example job_backend.docx, resume_anna.pdf, cv_rahul.pdf"),
        ("Summary quality (ROUGE)", "A human written summary", "for example reference_summary.txt"),
        ("NLP Playground", "Nothing", "type your own text"),
    ], columns=["page", "what to upload", "file name tip"])
    st.dataframe(guide, width="stretch", hide_index=True)
    panel("Why file names matter", "The scanner reads file names to find roles automatically: <b>job</b> for a job description, <b>resume</b> or <b>cv</b> for resumes, "
                                   "<b>reference</b> for a reference summary, and the same name with different numbers (<b>_v1</b>, <b>_v2</b>, <b>2024</b>, <b>2025</b>) for versions. "
                                   "You can still compare or match any files by choosing them on each page.")


def main():
    html(CSS)
    with st.sidebar:
        html('<div class="brand"><div class="logo">NS</div><div><div class="name">NLP Scanner</div><div class="sub">Classic NLP, no AI keys</div></div></div>')
        page = st.radio("Pages", PAGES, label_visibility="collapsed", format_func=lambda name: name)
        html(f'<div class="side-note">{escape(PAGE_NOTES[page])}</div>')
        st.markdown("---")
        uploads = st.file_uploader("Upload your documents", type=["txt", "md", "csv", "pdf", "docx", "html", "htm"], accept_multiple_files=True)
        st.session_state.setdefault("pasted", {})
        with st.expander("Or paste text as a document"):
            pasted_name = st.text_input("Document name", "my_notes.txt")
            pasted_text = st.text_area("Text", "", height=120)
            if st.button("Add this text") and pasted_text.strip():
                name = pasted_name.strip() or "pasted_text.txt"
                st.session_state["pasted"][name if "." in name else name + ".txt"] = pasted_text
            if st.session_state["pasted"]:
                st.caption("Pasted: " + ", ".join(st.session_state["pasted"].keys()))
                if st.button("Remove pasted texts"):
                    st.session_state["pasted"] = {}
                    st.rerun()
        with st.expander("Settings"):
            skill_threshold = st.slider("Skill similarity threshold", 0.40, 0.90, 0.60, 0.05)
            version_similarity = st.slider("Similarity to count as a version", 0.10, 0.90, 0.35, 0.05)
            topic_similarity = st.slider("Similarity to group topics", 0.05, 0.60, 0.12, 0.01)
        html('<div class="side-note">Tip: name files like report_v1.pdf and report_v2.pdf, resume_anna.pdf and job_backend.docx so roles are found automatically.</div>')

    documents = dict(st.session_state["pasted"])
    for upload in uploads or []:
        text = read_upload(upload.name, upload.getvalue())
        if text.strip():
            documents[upload.name] = text
        else:
            st.sidebar.warning(f"{upload.name} has no readable text (it may be a scanned PDF).")
    if not documents:
        welcome()
        return

    items = tuple(sorted(documents.items()))
    key = hashlib.md5(json.dumps([items, skill_threshold]).encode("utf-8")).hexdigest()
    with st.spinner("Reading and indexing the documents"):
        corpus = build_corpus(items, skill_threshold)
        roles = cached_roles(key, corpus, version_similarity, topic_similarity)

    if page == "Dashboard":
        dashboard(corpus, roles, key)
    elif page == "Document Explorer":
        explorer(corpus, key)
    elif page == "Compare Documents":
        compare_page(corpus, roles)
    elif page == "Resume Matcher":
        resume_page(corpus, roles, key)
    elif page == "Summarizer":
        summarizer_page(corpus, roles)
    elif page == "Ask Questions":
        ask_page(corpus)
    elif page == "Knowledge Graph":
        graph_page(corpus, roles, key)
    elif page == "NLP Playground":
        playground_page(corpus)
    elif page == "Quality and Drift":
        quality_page(corpus, roles)
    else:
        report_page(corpus, roles, key)
    html('<div class="footer">Multi Document NLP Scanner &middot; NLTK, scikit-learn, NumPy, Plotly, ReportLab &middot; no AI API keys</div>')


main()
