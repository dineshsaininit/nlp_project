import io
import os
import json
import threading
import webbrowser
import numpy as np
import pandas as pd
import networkx as nx
import plotly
from flask import Flask, request, jsonify, send_file, Response
from werkzeug.exceptions import HTTPException
import nlp_engine as engine

HERE = os.path.dirname(os.path.abspath(__file__))
PLOTLY_FILE = os.path.join(os.path.dirname(plotly.__file__), "package_data", "plotly.min.js")
PORT = 5000

app = Flask(__name__, static_folder=os.path.join(HERE, "static"), static_url_path="/static")
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024


class Workspace:
    def __init__(self):
        self.documents = {}
        self.settings = {"skill_threshold": 0.60, "version_similarity": 0.35, "topic_similarity": 0.12}
        self.corpus = None
        self.roles = None
        self.cache = {}
        self.lock = threading.Lock()

    def rebuild(self):
        self.cache = {}
        if not self.documents:
            self.corpus = None
            self.roles = None
            return
        self.corpus = engine.Corpus(self.documents, self.settings["skill_threshold"])
        self.roles = engine.detect_roles(self.corpus, self.settings["version_similarity"], self.settings["topic_similarity"])

    def remember(self, key, maker):
        if key not in self.cache:
            self.cache[key] = maker()
        return self.cache[key]


workspace = Workspace()


def clean(value):
    if isinstance(value, pd.DataFrame):
        return clean(value.to_dict(orient="records"))
    if isinstance(value, pd.Series):
        return clean(value.tolist())
    if isinstance(value, dict):
        return {str(key): clean(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(item) for item in value]
    if isinstance(value, set):
        return sorted(clean(item) for item in value)
    if isinstance(value, np.ndarray):
        return clean(value.tolist())
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, (float, np.floating)):
        number = float(value)
        return None if number != number else number
    return value


def reply(value):
    return jsonify(clean(value))


def body():
    return request.get_json(silent=True) or {}


def need_documents():
    if workspace.corpus is None:
        return jsonify({"error": "Add some documents first."}), 400
    return None


def check_names(names):
    missing = [name for name in names if name not in workspace.corpus.names]
    if missing:
        raise ValueError("Unknown document: " + ", ".join(missing))


@app.errorhandler(Exception)
def handle_error(error):
    if isinstance(error, HTTPException):
        return jsonify({"error": error.description}), error.code
    return jsonify({"error": str(error)}), 500


@app.get("/")
def index():
    return send_file(os.path.join(HERE, "static", "index.html"))


@app.get("/vendor/plotly.min.js")
def plotly_script():
    return send_file(PLOTLY_FILE, mimetype="application/javascript", max_age=86400)


@app.get("/api/state")
def state():
    documents = []
    for name, text in workspace.documents.items():
        documents.append({"name": name, "type": os.path.splitext(name)[1].lstrip(".").lower() or "txt", "characters": len(text)})
    return reply({"documents": documents, "roles": workspace.roles, "settings": workspace.settings})


@app.post("/api/upload")
def upload():
    added, skipped = [], []
    for file in request.files.getlist("files"):
        name = os.path.basename(file.filename or "")
        if not name.lower().endswith(engine.SUPPORTED_TYPES):
            skipped.append(f"{name}: this file type is not supported")
            continue
        try:
            text = engine.read_bytes(name, file.read())
        except Exception as error:
            skipped.append(f"{name}: could not be read ({error})")
            continue
        if not text.strip():
            skipped.append(f"{name}: no readable text, it may be a scanned PDF")
            continue
        workspace.documents[name] = text
        added.append(name)
    with workspace.lock:
        workspace.rebuild()
    return reply({"added": added, "skipped": skipped})


@app.post("/api/paste")
def paste():
    data = body()
    text = (data.get("text") or "").strip()
    name = (data.get("name") or "pasted_text.txt").strip()
    if not text:
        return jsonify({"error": "The text is empty."}), 400
    if "." not in name:
        name += ".txt"
    workspace.documents[name] = text
    with workspace.lock:
        workspace.rebuild()
    return reply({"added": [name]})


@app.delete("/api/documents/<path:name>")
def remove_document(name):
    workspace.documents.pop(name, None)
    with workspace.lock:
        workspace.rebuild()
    return reply({"removed": name})


@app.post("/api/clear")
def clear():
    workspace.documents = {}
    with workspace.lock:
        workspace.rebuild()
    return reply({"cleared": True})


@app.post("/api/settings")
def settings():
    data = body()
    for key in workspace.settings:
        if key in data:
            workspace.settings[key] = float(data[key])
    with workspace.lock:
        workspace.rebuild()
    return reply(workspace.settings)


def overview():
    return workspace.remember("overview", lambda: engine.overview_table(workspace.corpus))


@app.get("/api/overview")
def overview_api():
    blocked = need_documents()
    if blocked:
        return blocked
    corpus = workspace.corpus

    def build():
        table = overview()
        topic_words, topic_table = engine.find_topics(corpus)
        items = [(name, sentence) for name in corpus.names for sentence in corpus.sentences[name]]
        points = engine.sentence_map(corpus.vectorizer, items)
        topics = [{"words": words, "documents": topic_table[topic_table["main topic"] == f"Topic {index + 1}"]["document"].tolist()}
                  for index, words in enumerate(topic_words)]
        return {
            "names": corpus.names,
            "table": table,
            "similarity": corpus.similarity,
            "points": points,
            "topics": topics,
            "totals": {"documents": len(corpus.names), "words": int(table["words"].sum()), "sentences": len(corpus.all_sentences),
                       "vocabulary": len(corpus.vectorizer.word_model.vocabulary_), "topics": len(topic_words),
                       "versions": len(workspace.roles["version_groups"])},
            "roles": workspace.roles,
        }

    return reply(workspace.remember("overview page", build))


@app.get("/api/document")
def document_api():
    blocked = need_documents()
    if blocked:
        return blocked
    corpus = workspace.corpus
    name = request.args.get("name") or corpus.names[0]
    check_names([name])

    def build():
        text = corpus.documents[name]
        doc_type, type_confidence, type_scores = engine.detect_document_type(text)
        language, language_confidence, language_scores = engine.detect_language(text)
        mood_score, mood = engine.sentiment(text)
        summary, trace = engine.summarize(corpus, [name], 3)
        entities = corpus.entities(name)
        return {
            "name": name,
            "text": text,
            "words": len(engine.alpha_words(text)),
            "sentences": len(corpus.sentences[name]),
            "readability": engine.readability_scores(text),
            "style": engine.style_profile(text),
            "mood": {"score": mood_score, "label": mood},
            "type": {"label": doc_type, "confidence": type_confidence, "scores": type_scores},
            "language": {"label": language, "confidence": language_confidence, "scores": language_scores},
            "summary": summary,
            "keywords": corpus.keyword_weights(name, 30),
            "rake": engine.rake_keyphrases(text, 12),
            "pairs": engine.word_pairs(text, 12),
            "arc": engine.sentiment_arc(text),
            "entities": {label: counter.most_common(15) for label, counter in entities.items() if counter},
            "skills": corpus.skills[name],
            "zipf": engine.zipf_table(text).head(300),
        }

    return reply(workspace.remember(("document", name), build))


def alignment(corpus, old_text, new_text):
    old_sentences = [engine.strip_numbering(s) for s in engine.split_sentences(old_text)]
    new_sentences = [engine.strip_numbering(s) for s in engine.split_sentences(new_text)]
    if not old_sentences or not new_sentences or len(old_sentences) * len(new_sentences) > 6400:
        return None
    steps, matrix = engine.needleman_wunsch(old_sentences, new_sentences, engine.vectorizer_for(corpus, old_text, new_text))
    path = [[0, 0]]
    i = j = 0
    for label, old_sentence, new_sentence, value in steps:
        if label in ("SAME", "CHANGED"):
            i, j = i + 1, j + 1
        elif label == "ADDED":
            j += 1
        else:
            i += 1
        path.append([i, j])
    return {"matrix": matrix.round(2), "path": path, "rows": old_sentences, "columns": new_sentences}


@app.post("/api/compare")
def compare_api():
    blocked = need_documents()
    if blocked:
        return blocked
    corpus = workspace.corpus
    data = body()
    if data.get("mode") == "text":
        old_text, new_text = data.get("old_text") or "", data.get("new_text") or ""
        if not old_text.strip() or not new_text.strip():
            return jsonify({"error": "Type some text in both boxes."}), 400
        result = engine.compare_texts(corpus, old_text, new_text)
        old_name = new_name = None
    else:
        old_name, new_name = data.get("old"), data.get("new")
        check_names([old_name, new_name])
        old_text, new_text = corpus.documents[old_name], corpus.documents[new_name]
        result = engine.compare_documents(corpus, old_name, new_name)
    steps = []
    for label, old_sentence, new_sentence, value in result.pop("steps"):
        steps.append({"label": label, "old": old_sentence, "new": new_sentence, "value": round(value, 2),
                      "words": engine.word_diff_html(old_sentence, new_sentence) if label == "CHANGED" else ""})
    result["steps"] = steps
    result["copy"] = engine.copy_check(old_text, new_text)
    result["alignment"] = alignment(corpus, old_text, new_text)
    group = next((group for group in workspace.roles["version_groups"] if old_name in group and new_name in group), None)
    timeline = []
    if group:
        for first, second in zip(group, group[1:]):
            step = engine.compare_documents(corpus, first, second)
            timeline.append({"from": first, "to": second, "similarity": step["similarity"], **step["counts"]})
    result["timeline"] = timeline
    return reply(result)


@app.post("/api/match")
def match_api():
    blocked = need_documents()
    if blocked:
        return blocked
    corpus = workspace.corpus
    data = body()
    job = data.get("job")
    resumes = data.get("resumes") or []
    check_names([job] + resumes)
    if not resumes:
        return jsonify({"error": "Choose at least one resume."}), 400
    job_text = (data.get("job_text") or "").strip() or corpus.documents[job]
    results = {}
    for name in resumes:
        results[name] = workspace.remember(("match", hash(job_text), name), lambda name=name: engine.match_resume(corpus, job_text, corpus.documents[name]))
    ordered = sorted(results, key=lambda name: results[name]["final_score"], reverse=True)
    return reply({
        "ordered": ordered,
        "results": results,
        "job_skills": results[ordered[0]]["job_skills"],
        "read_text": {name: engine.remove_personal_details(corpus.documents[name]).strip() for name in resumes},
    })


@app.post("/api/fairness")
def fairness_api():
    blocked = need_documents()
    if blocked:
        return blocked
    data = body()
    check_names([data.get("job")] + (data.get("resumes") or []))
    return reply(engine.fairness_check(workspace.corpus, data["job"], data.get("resumes") or []))


@app.post("/api/summary")
def summary_api():
    blocked = need_documents()
    if blocked:
        return blocked
    corpus = workspace.corpus
    data = body()
    files = data.get("files") or []
    check_names(files)
    if not files:
        return jsonify({"error": "Choose at least one document."}), 400
    size = int(data.get("size") or 4)
    summary, trace = engine.summarize(corpus, files, size)
    source_words = sum(len(engine.alpha_words(corpus.documents[name])) for name in files)
    reference = (data.get("reference_text") or "").strip()
    if not reference and data.get("reference") in corpus.names:
        reference = corpus.documents[data["reference"]]
    evaluation = None
    if reference and summary:
        evaluation = engine.evaluate_summary(corpus, summary, reference).reset_index().rename(columns={"index": "metric"})
    return reply({"summary": summary, "trace": trace, "source_words": source_words,
                  "summary_words": len(engine.alpha_words(summary)), "evaluation": evaluation})


@app.get("/api/singles")
def singles_api():
    blocked = need_documents()
    if blocked:
        return blocked
    corpus = workspace.corpus
    return reply(workspace.remember("singles", lambda: [{"document": name, "summary": engine.summarize(corpus, [name], 2)[0]} for name in corpus.names]))


@app.get("/api/examples")
def examples_api():
    blocked = need_documents()
    if blocked:
        return blocked
    corpus = workspace.corpus
    keywords = []
    for name in corpus.names:
        for keyword in corpus.top_keywords(name, 3):
            if keyword not in keywords and " " not in keyword:
                keywords.append(keyword)
                break
    questions = [f"What is said about {keyword}?" for keyword in keywords[:4]]
    questions += ["How many days, people or items are mentioned?", "Where does this take place?"]
    return reply(questions)


@app.post("/api/ask")
def ask_api():
    blocked = need_documents()
    if blocked:
        return blocked
    data = body()
    question = (data.get("question") or "").strip()
    if not question:
        return jsonify({"error": "Type a question first."}), 400
    only = data.get("only") or None
    answer = engine.answer_question(question, workspace.corpus.store, top_k=int(data.get("top_k") or 5), only_from=only)
    answer["terms"] = sorted({word for word in engine.word_tokenize(question.lower()) if word.isalpha() and word not in engine.stop_words})
    return reply(answer)


@app.post("/api/graph")
def graph_api():
    blocked = need_documents()
    if blocked:
        return blocked
    corpus = workspace.corpus
    files = body().get("files") or []
    check_names(files)
    frames = [workspace.remember(("triples", name), lambda name=name: engine.find_triples(corpus.documents[name])).assign(document=name) for name in files]
    triples = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=["subject", "relation", "object", "sentence", "document"])
    if triples.empty:
        return reply({"triples": [], "nodes": [], "edges": []})
    graph = engine.build_graph(triples)
    layout = nx.spring_layout(graph, seed=7, k=1.4 / max(graph.number_of_nodes() ** 0.5, 1))
    degrees = dict(graph.degree)
    nodes = [{"id": node, "x": float(layout[node][0]), "y": float(layout[node][1]), "degree": degrees[node]} for node in graph.nodes]
    edges = [{"source": start, "target": end, "label": data["label"]} for start, end, data in graph.edges(data=True)]
    return reply({"triples": triples[["document", "subject", "relation", "object", "sentence"]], "nodes": nodes, "edges": edges})


@app.post("/api/pipeline")
def pipeline_api():
    sentence = (body().get("text") or "").strip()
    return reply(engine.nlp_pipeline(sentence) if sentence else [])


@app.post("/api/meaning")
def meaning_api():
    word = (body().get("text") or "").strip()
    return reply(engine.word_meaning(word, 6) if word else [])


@app.post("/api/language")
def language_api():
    text = (body().get("text") or "").strip()
    if not text:
        return reply(None)
    language, confidence, scores = engine.detect_language(text)
    return reply({"language": language, "confidence": confidence, "scores": scores})


@app.post("/api/redact")
def redact_api():
    data = body()
    text = data.get("text") or ""
    if data.get("name") and workspace.corpus and data["name"] in workspace.corpus.names:
        text = workspace.corpus.documents[data["name"]]
    redacted, counts = engine.redact_text(text)
    return reply({"original": text, "redacted": redacted, "counts": counts})


@app.post("/api/skills")
def skills_api():
    text = (body().get("text") or "").strip()
    finder = workspace.corpus.skill_finder if workspace.corpus else workspace.remember("finder", lambda: engine.SkillFinder())
    found, rejected = finder.extract(text) if text else ({}, [])
    return reply({"found": found, "rejected": rejected})


@app.get("/api/quality")
def quality_api():
    blocked = need_documents()
    if blocked:
        return blocked
    corpus = workspace.corpus
    threshold = float(request.args.get("threshold") or 0.8)
    drift_table, unusual_table = engine.drift_report(corpus, workspace.roles["version_groups"])
    shared = engine.shared_sentences(corpus, workspace.roles["version_groups"], threshold)
    return reply({"drift": drift_table, "unusual": unusual_table, "shared": shared})


@app.post("/api/tests")
def tests_api():
    blocked = need_documents()
    if blocked:
        return blocked
    return reply({"tests": engine.run_self_tests(workspace.corpus), "benchmark": engine.run_benchmark(workspace.corpus, workspace.roles)})


@app.get("/api/report")
def report_api():
    blocked = need_documents()
    if blocked:
        return blocked
    data = engine.build_report(workspace.corpus, workspace.roles)
    return send_file(io.BytesIO(data), mimetype="application/pdf", as_attachment=True, download_name="nlp_scanner_report.pdf")


@app.get("/api/export.csv")
def export_csv():
    blocked = need_documents()
    if blocked:
        return blocked
    return Response(overview().to_csv(index=False), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=document_overview.csv"})


@app.get("/api/export.json")
def export_json():
    blocked = need_documents()
    if blocked:
        return blocked
    corpus = workspace.corpus
    data = {
        "roles": workspace.roles,
        "documents": overview(),
        "details": {name: {"keywords": corpus.top_keywords(name, 10),
                           "key phrases": [phrase for phrase, score in engine.rake_keyphrases(corpus.documents[name], 8)],
                           "skills": list(corpus.skills[name].keys()),
                           "summary": engine.summarize(corpus, [name], 2)[0]} for name in corpus.names},
    }
    return Response(json.dumps(clean(data), indent=2), mimetype="application/json",
                    headers={"Content-Disposition": "attachment; filename=analysis.json"})


if __name__ == "__main__":
    address = f"http://127.0.0.1:{PORT}"
    print(f"Document Scanner is running at {address}")
    print("Press Ctrl + C to stop it")
    threading.Timer(1.5, lambda: webbrowser.open(address)).start()
    app.run(host="127.0.0.1", port=PORT, debug=False, threaded=True)
