import io
import os
import re
import time
import math
import difflib
import numpy as np
import pandas as pd
import nltk
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from collections import Counter
from xml.sax.saxutils import escape
from nltk.tokenize import word_tokenize, PunktTokenizer
from nltk.corpus import stopwords, wordnet
from nltk.stem import WordNetLemmatizer, PorterStemmer
from nltk.chunk import ne_chunker
from nltk.sentiment import SentimentIntensityAnalyzer
from nltk.collocations import BigramCollocationFinder
from nltk.metrics import BigramAssocMeasures
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize
from sklearn.decomposition import NMF, PCA
from sklearn.cluster import AgglomerativeClustering
import networkx as nx
from scipy.spatial.distance import jensenshannon
from pypdf import PdfReader
from docx import Document as WordDocument
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.platypus import Image as PdfImage

NLTK_RESOURCES = {
    "punkt": "tokenizers/punkt",
    "punkt_tab": "tokenizers/punkt_tab",
    "stopwords": "corpora/stopwords",
    "wordnet": "corpora/wordnet",
    "omw-1.4": "corpora/omw-1.4",
    "averaged_perceptron_tagger": "taggers/averaged_perceptron_tagger",
    "averaged_perceptron_tagger_eng": "taggers/averaged_perceptron_tagger_eng",
    "maxent_ne_chunker": "chunkers/maxent_ne_chunker",
    "maxent_ne_chunker_tab": "chunkers/maxent_ne_chunker_tab",
    "words": "corpora/words",
    "vader_lexicon": "sentiment/vader_lexicon.zip",
}


def prepare_nltk():
    for package, path in NLTK_RESOURCES.items():
        try:
            nltk.data.find(path)
        except LookupError:
            nltk.download(package, quiet=True)


prepare_nltk()

stop_words = set(stopwords.words("english"))
lemmatizer = WordNetLemmatizer()
stemmer = PorterStemmer()
sentiment_tool = SentimentIntensityAnalyzer()
entity_chunker = ne_chunker()
short_names = {"nlp": "natural language processing", "ml": "machine learning", "ai": "artificial intelligence",
               "js": "javascript", "hr": "human resources", "ui": "user interface"}
END_MARKS = (".", "!", "?", ":", ";")
SUPPORTED_TYPES = (".txt", ".md", ".csv", ".pdf", ".docx", ".html", ".htm")
month_names = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?"
full_months = r"(?:january|february|march|april|june|july|august|september|october|november|december)"
month_pattern = (r"\b\d{1,2}(?:st|nd|rd|th)?\s+" + month_names + r"(?:,?\s+\d{4})?(?![a-z])"
                 + r"|\b" + month_names + r"\s+\d{1,2}(?:st|nd|rd|th)?(?:,\s*\d{4})?\b"
                 + r"|\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b"
                 + r"|\b" + full_months + r"(?:\s+\d{4})?\b"
                 + r"|\b(?:19|20)\d{2}\b")
number_pattern = r"\b\d{1,3}(?:,\d{3})+(?:\.\d+)?\b|\b\d+(?:\.\d+)?%?"
sentence_splitter = PunktTokenizer("english")
sentence_splitter._params.abbrev_types.update({
    "rs", "pvt", "ltd", "inc", "co", "corp", "dr", "mr", "mrs", "ms", "prof", "no", "nos", "vs", "etc", "approx", "dept",
    "fig", "sec", "st", "jr", "sr", "b.tech", "m.tech", "b.sc", "m.sc", "b.e", "m.e", "b.com", "ph.d", "e.g", "i.e", "u.s",
})
BULLETS = "-*\u2022\u25aa\u25cf\u25e6\u2023\u2043\u00b7\uf0b7\uf0a7\x7f "
PAGE_NUMBER = re.compile(r"^\s*(?:page\s*)?\d{1,4}(?:\s*(?:of|/)\s*\d{1,4})?\s*$", re.IGNORECASE)


def tidy_text(text):
    text = text.replace("\r", "\n").replace("\u00a0", " ")
    for fancy, plain in [("\u2018", "'"), ("\u2019", "'"), ("\u201c", '"'), ("\u201d", '"'), ("\u2013", "-"), ("\u2014", "-"), ("\ufb01", "fi"), ("\ufb02", "fl")]:
        text = text.replace(fancy, plain)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", " ", text)
    text = re.sub(r"([a-z])-\n([a-z])", r"\1\2", text)
    return text


def remove_page_furniture(pages):
    def shape(line):
        return re.sub(r"\d+", "#", line.strip().lower())

    edges = Counter()
    for page in pages:
        lines = [line.strip() for line in page.split("\n") if line.strip()]
        for line in set(lines[:3] + lines[-3:]):
            edges[shape(line)] += 1
    repeated = {key for key, count in edges.items() if count >= 2} if len(pages) >= 2 else set()
    cleaned = []
    for page in pages:
        lines = [line for line in page.split("\n") if line.strip()]
        keep = []
        for index, line in enumerate(lines):
            near_edge = index < 3 or index >= len(lines) - 3
            if PAGE_NUMBER.match(line) or (near_edge and shape(line) in repeated):
                continue
            keep.append(line)
        cleaned.append("\n".join(keep))
    return "\n".join(cleaned)


def read_bytes(file_name, data):
    extension = os.path.splitext(file_name)[1].lower()
    if extension == ".pdf":
        reader = PdfReader(io.BytesIO(data))
        pages = [tidy_text(page.extract_text() or "") for page in reader.pages]
        return remove_page_furniture(pages)
    if extension == ".docx":
        word_file = WordDocument(io.BytesIO(data))
        lines = [paragraph.text for paragraph in word_file.paragraphs]
        for table in word_file.tables:
            for row in table.rows:
                lines.append(" | ".join(box.text for box in row.cells))
        return tidy_text("\n".join(lines))
    text = data.decode("utf-8", errors="ignore")
    if extension in (".html", ".htm"):
        text = re.sub(r"(?is)<(script|style).*?</\1>", " ", text)
        text = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</li>|</h\d>", "\n", text)
        text = re.sub(r"<[^>]+>", " ", text)
    return tidy_text(text)


def read_path(path):
    with open(path, "rb") as file:
        return read_bytes(os.path.basename(path), file.read())


def load_folder(folder):
    documents = {}
    for file_name in sorted(os.listdir(folder)):
        if file_name.lower().endswith(SUPPORTED_TYPES):
            text = read_path(os.path.join(folder, file_name))
            if text.strip():
                documents[file_name] = text
    return documents


def clean_text(text):
    text = text.replace("\t", " ").replace("\r", "")
    text = re.sub(r"[ ]+", " ", text)
    return text.strip()


def split_sentences(text):
    lines = [line.strip().strip(BULLETS).strip() for line in clean_text(tidy_text(text)).split("\n")]
    blocks = []
    buffer = ""
    for index, line in enumerate(lines):
        if not line:
            if buffer:
                blocks.append(buffer)
                buffer = ""
            continue
        buffer = (buffer + " " + line).strip()
        next_line = lines[index + 1] if index + 1 < len(lines) else ""
        keep_going = (not line.endswith(END_MARKS)) and next_line and (next_line[0].islower() or len(line) >= 75)
        if not keep_going:
            blocks.append(buffer)
            buffer = ""
    if buffer:
        blocks.append(buffer)
    sentences = []
    for block in blocks:
        for sentence in sentence_splitter.tokenize(block):
            if len(sentence.strip()) > 2:
                sentences.append(sentence.strip())
    return sentences


def get_tokens(text):
    good_words = []
    for word in word_tokenize(text.lower()):
        if word.isalpha() and word not in stop_words:
            for part in short_names.get(word, word).split():
                good_words.append(lemmatizer.lemmatize(part))
    return good_words


def preprocess(text):
    return " ".join(get_tokens(text))


def preprocess_for_vectors(text):
    return " ".join(stemmer.stem(word) for word in get_tokens(text))


def alpha_words(text):
    return [word for word in word_tokenize(text) if word.isalpha()]


class TextVectorizer:
    def __init__(self):
        self.word_model = TfidfVectorizer(preprocessor=preprocess_for_vectors, ngram_range=(1, 2), sublinear_tf=True)
        self.char_model = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), lowercase=True, sublinear_tf=True)

    def fit(self, texts):
        self.word_model.fit(texts)
        self.char_model.fit(texts)
        return self

    def transform(self, texts):
        word_vectors = normalize(self.word_model.transform(texts).toarray())
        char_vectors = normalize(self.char_model.transform(texts).toarray())
        joined = np.hstack([word_vectors * np.sqrt(0.5), char_vectors * np.sqrt(0.5)])
        return normalize(joined)


def cosine_matrix(vectors_a, vectors_b):
    return np.clip(vectors_a @ vectors_b.T, 0, 1)


class VectorStore:
    def __init__(self, vectorizer):
        self.vectorizer = vectorizer
        self.texts = []
        self.sources = []
        self.vectors = None

    def add(self, texts, source):
        if not texts:
            return
        new_vectors = self.vectorizer.transform(texts)
        self.vectors = new_vectors if self.vectors is None else np.vstack([self.vectors, new_vectors])
        self.texts.extend(texts)
        self.sources.extend([source] * len(texts))

    def search(self, query, top_k=3, only_from=None, min_words=4):
        if self.vectors is None or not query.strip():
            return []
        query_vector = self.vectorizer.transform([query])[0]
        scores = self.vectors @ query_vector
        results = []
        for position in np.argsort(scores)[::-1]:
            if only_from and self.sources[position] not in only_from:
                continue
            if len(self.texts[position].split()) < min_words:
                continue
            results.append({"source": self.sources[position], "text": self.texts[position], "score": round(float(scores[position]), 3)})
            if len(results) == top_k:
                break
        return results


skill_taxonomy = {
    "JavaScript": ["javascript", "frontend scripting", "front end scripting", "vanilla javascript", "ecmascript", "typescript"],
    "React": ["react", "reactjs", "react js"],
    "Node.js": ["node", "nodejs", "node js", "express"],
    "Python": ["python", "python programming"],
    "Java": ["java", "spring boot"],
    "C and C++": ["c++", "cpp", "c programming"],
    "HTML": ["html", "html5"],
    "CSS": ["css", "css3", "tailwind", "bootstrap"],
    "SQL": ["sql", "mysql", "postgresql", "sql databases", "database queries", "oracle database"],
    "NoSQL": ["mongodb", "nosql", "redis"],
    "REST API": ["rest api", "rest apis", "api endpoints", "web services"],
    "Git": ["git", "github", "gitlab", "version control"],
    "Docker": ["docker", "docker containers", "kubernetes"],
    "Cloud Computing": ["aws", "azure", "cloud platforms", "cloud computing", "google cloud"],
    "Linux": ["linux", "unix", "shell scripting", "bash"],
    "Machine Learning": ["machine learning", "predictive modelling", "predictive modeling", "scikit learn", "classification models"],
    "Deep Learning": ["deep learning", "neural networks", "tensorflow", "pytorch"],
    "Natural Language Processing": ["natural language processing", "text mining", "text processing"],
    "Data Analysis": ["data analysis", "analysed data", "analyzed data", "pandas", "excel", "numpy"],
    "Data Visualisation": ["tableau", "power bi", "data visualisation", "data visualization", "matplotlib", "seaborn", "plotly"],
    "Statistics": ["statistics", "statistical analysis", "probability"],
    "Testing": ["unit testing", "pytest", "selenium", "test automation"],
    "Project Management": ["project management", "agile", "scrum", "jira"],
    "Communication": ["communication", "communication skills", "presentation skills", "public speaking", "presented", "presenting",
                      "presentation", "presentations", "explain results", "explaining results"],
    "Teamwork": ["teamwork", "team player", "work in a team", "collaboration"],
    "Leadership": ["leadership", "team lead", "mentoring"],
    "Problem Solving": ["problem solving", "analytical thinking", "critical thinking"],
    "UI Design": ["figma", "wireframes", "prototypes", "user interfaces", "ui design", "user interface design"],
    "Graphic Design": ["photoshop", "illustrator", "graphic design"],
    "User Research": ["user research", "user testing", "usability testing"],
    "Accounting": ["accounting", "bookkeeping", "tally", "financial reporting"],
    "Marketing": ["digital marketing", "seo", "social media marketing", "content marketing"],
    "Teaching": ["teaching", "lesson planning", "curriculum design"],
    "Polish Language": ["polish", "polish language"],
}
words_that_can_be_verbs = {"polish", "react", "node", "express", "teaching"}
false_friends = {"leadership": ["leadership team", "leadership group", "the leadership"], "react": ["react quickly", "react to"],
                 "presentation": ["presentation layer"], "excel": ["excel at", "excel in"]}
phrase_to_skill = {}
for skill_name, phrases in skill_taxonomy.items():
    for phrase in phrases:
        phrase_to_skill[phrase] = skill_name
taxonomy_phrases = list(phrase_to_skill.keys())
noun_phrase_grammar = nltk.RegexpParser("PHRASE: {<JJ|NN.*>*<NN.*>}")


def tag_sentence(sentence):
    sentence = sentence.replace("-", " ").replace(".js", "js").replace("/", " , ")
    return nltk.pos_tag(word_tokenize(sentence))


def exact_skill_matches(tagged_words, found, rejected):
    lower_words = [word.lower() for word, tag in tagged_words]
    for size in [3, 2, 1]:
        for start in range(len(lower_words) - size + 1):
            phrase = " ".join(lower_words[start:start + size])
            if phrase not in phrase_to_skill:
                continue
            if size == 1 and phrase in words_that_can_be_verbs and tagged_words[start][1].startswith("VB"):
                rejected.append(f"'{phrase}' is used as a verb here, so it is not counted as a skill")
                continue
            context = " ".join(lower_words[max(0, start - 1):start + size + 2])
            friend = next((item for item in false_friends.get(phrase, []) if item in context), None)
            if friend:
                rejected.append(f"'{phrase}' is part of '{friend}' here, so it is not counted as a skill")
                continue
            if phrase_to_skill[phrase] not in found:
                found[phrase_to_skill[phrase]] = phrase


class SkillFinder:
    def __init__(self, extra_sentences=(), threshold=0.60):
        self.threshold = threshold
        self.vectorizer = TextVectorizer().fit(taxonomy_phrases + list(extra_sentences))
        self.taxonomy_vectors = self.vectorizer.transform(taxonomy_phrases)

    def similar_skill_matches(self, tagged_words, found):
        tree = noun_phrase_grammar.parse(tagged_words)
        for subtree in tree.subtrees(filter=lambda part: part.label() == "PHRASE"):
            phrase = " ".join(word for word, tag in subtree.leaves()).lower()
            if len(phrase) < 3 or any(friend in phrase for friends in false_friends.values() for friend in friends):
                continue
            scores = cosine_matrix(self.vectorizer.transform([phrase]), self.taxonomy_vectors)[0]
            best = int(np.argmax(scores))
            skill_name = phrase_to_skill[taxonomy_phrases[best]]
            if scores[best] >= self.threshold and skill_name not in found:
                found[skill_name] = f"{phrase} (similarity {scores[best]:.2f})"

    def extract(self, text):
        found = {}
        rejected = []
        for sentence in split_sentences(text):
            tagged_words = tag_sentence(sentence)
            exact_skill_matches(tagged_words, found, rejected)
            self.similar_skill_matches(tagged_words, found)
        return found, rejected


known_places = {
    "india", "delhi", "new delhi", "mumbai", "bombay", "bengaluru", "bangalore", "pune", "hyderabad", "chennai", "kolkata", "gangtok",
    "sikkim", "ahmedabad", "jaipur", "lucknow", "noida", "gurugram", "gurgaon", "chandigarh", "kochi", "indore", "bhopal", "patna",
    "guwahati", "goa", "kerala", "karnataka", "maharashtra", "tamil nadu", "gujarat", "rajasthan", "punjab", "west bengal", "assam",
    "london", "paris", "berlin", "tokyo", "singapore", "dubai", "new york", "california", "texas", "sydney", "toronto", "beijing",
    "usa", "united states", "america", "uk", "united kingdom", "england", "germany", "france", "japan", "china", "canada",
    "australia", "nepal", "bhutan", "bangladesh", "sri lanka", "europe", "asia", "africa",
}
organisation_words = {"pvt", "ltd", "limited", "inc", "corp", "corporation", "llc", "llp", "university", "college", "institute",
                      "school", "bank", "company", "technologies", "solutions", "labs", "foundation", "department", "ministry", "agency"}
not_entities = {"rs", "inr", "usd", "eur", "gbp", "page", "name", "email", "phone"}
subjects = {"computer science", "information technology", "electronics", "mechanical engineering", "civil engineering",
            "electrical engineering", "data science", "mathematics", "physics", "chemistry", "commerce", "economics", "statistics"}


def find_name_line(text):
    head_lines = [line.strip() for line in text.split("\n") if line.strip()][:6]
    if not any("@" in line for line in head_lines):
        return ""
    for line in head_lines[:3]:
        words = line.split()
        if 2 <= len(words) <= 4 and all(word[:1].isupper() and word.replace(".", "").isalpha() for word in words) \
                and not any(word.lower() in stop_words or word.lower() in phrase_to_skill for word in words):
            return line
    return ""


def entity_label(words, label):
    lowered = " ".join(words).lower()
    plain = [word.lower().strip(".") for word in words]
    if lowered in known_places or all(word in known_places for word in plain):
        return "PLACE"
    if any(word in organisation_words for word in plain):
        return "ORGANIZATION" if len(words) > 1 else None
    return label


def is_real_entity(words, position, tagged, lowercase_words):
    if " ".join(words).lower().strip(".") in not_entities:
        return False
    lowered = " ".join(words).lower()
    if lowered in known_places:
        return True
    if lowered in subjects or any(phrase.startswith(lowered + " ") for phrase in taxonomy_phrases):
        return False
    if len(words) == 1 and position == 0:
        return False
    if all(word.lower() in lowercase_words for word in words):
        return False
    if any(word.lower() in phrase_to_skill for word in words) or " ".join(words).lower() in phrase_to_skill:
        return False
    next_position = position + len(words)
    if next_position < len(tagged) and tagged[next_position][0] == ":":
        return False
    return True


def find_entities(text, max_sentences=400):
    found = {"PERSON": Counter(), "ORGANIZATION": Counter(), "PLACE": Counter(), "DATE": Counter(),
             "NUMBER": Counter(), "MONEY": Counter(), "EMAIL": Counter(), "URL": Counter()}
    plain_text = re.sub(r"[\w.+-]+@[\w-]+\.[\w.]+|https?://\S+", " ", text)
    lowercase_words = {word for word in word_tokenize(plain_text) if word.islower()}
    for sentence in split_sentences(text)[:max_sentences]:
        tagged = nltk.pos_tag(word_tokenize(sentence))
        tree = entity_chunker.parse(tagged)
        position = 0
        for part in tree:
            if not hasattr(part, "label"):
                position += 1
                continue
            words = [word for word, tag in part.leaves()]
            start = position
            position += len(words)
            if not is_real_entity(words, start, tagged, lowercase_words):
                continue
            entity = " ".join(words)
            label = entity_label(words, part.label())
            if label is None:
                continue
            if label == "PERSON":
                found["PERSON"][entity] += 1
            elif label in ("ORGANIZATION", "FACILITY"):
                found["ORGANIZATION"][entity] += 1
            elif label in ("GPE", "LOCATION", "PLACE"):
                found["PLACE"][entity] += 1
    for place in known_places:
        for match in re.finditer(r"\b" + re.escape(place) + r"\b", text, flags=re.IGNORECASE):
            if match.group(0)[0].isupper() and match.group(0) not in found["PLACE"]:
                found["PLACE"][match.group(0)] += 1
                break
    name = find_name_line(text)
    if name:
        name_words = name.split()
        if True:
            for other in list(found["PERSON"]):
                if set(other.split()) <= set(name_words):
                    del found["PERSON"][other]
            for group in ("ORGANIZATION", "PLACE"):
                for other in list(found[group]):
                    if set(other.split()) <= set(name_words):
                        del found[group][other]
            found["PERSON"][name] += 1
    found["EMAIL"].update(item.rstrip(".") for item in re.findall(r"[\w.+-]+@[\w-]+\.[\w.]+", text))
    found["URL"].update(re.findall(r"https?://\S+|www\.\S+", text))
    found["DATE"].update(item.strip(" .,") for item in re.findall(month_pattern, text, flags=re.IGNORECASE))
    found["MONEY"].update(item.strip() for item in re.findall(r"(?:rs\.?|inr|usd|\$|\u20b9|\u20ac|\u00a3)\s?\d[\d,]*(?:\.\d+)?(?:\s?(?:lakh|crore|k|million))?", text, flags=re.IGNORECASE))
    found["NUMBER"].update(re.findall(r"\b\d+(?:\.\d+)?\s?(?:%|percent|days|years|months|hours|weeks)\b", text, flags=re.IGNORECASE))
    return found


def count_syllables(word):
    word = word.lower()
    count = len(re.findall(r"[aeiouy]+", word))
    if word.endswith("e") and count > 1:
        count -= 1
    return max(count, 1)


def readability(text):
    sentences = split_sentences(text)
    words = alpha_words(text)
    if not sentences or not words:
        return 0.0
    syllables = sum(count_syllables(word) for word in words)
    return round(206.835 - 1.015 * len(words) / len(sentences) - 84.6 * syllables / len(words), 1)


def reading_level(score):
    if score >= 70:
        return "Easy"
    if score >= 50:
        return "Medium"
    if score >= 30:
        return "Hard"
    return "Very hard"


def sentiment(text):
    scores = [sentiment_tool.polarity_scores(sentence)["compound"] for sentence in split_sentences(text)]
    average = float(np.mean(scores)) if scores else 0.0
    label = "Positive" if average > 0.05 else "Negative" if average < -0.05 else "Neutral"
    return round(average, 3), label


class Corpus:
    def __init__(self, documents, skill_threshold=0.60):
        if not documents:
            raise ValueError("No documents were given")
        self.documents = dict(documents)
        self.names = list(self.documents.keys())
        self.sentences = {name: split_sentences(text) for name, text in self.documents.items()}
        self.all_sentences = [sentence for name in self.names for sentence in self.sentences[name]]
        texts = [self.documents[name] for name in self.names]
        self.vectorizer = TextVectorizer().fit(self.all_sentences + texts)
        self.doc_vectors = self.vectorizer.transform(texts)
        self.similarity = cosine_matrix(self.doc_vectors, self.doc_vectors)
        self.keyword_model = TfidfVectorizer(preprocessor=preprocess, ngram_range=(1, 2), sublinear_tf=True)
        self.keyword_matrix = self.keyword_model.fit_transform(texts)
        self.keyword_terms = np.array(self.keyword_model.get_feature_names_out())
        self.store = VectorStore(self.vectorizer)
        for name in self.names:
            self.store.add(self.sentences[name], name)
        self.skill_finder = SkillFinder(self.all_sentences, skill_threshold)
        self.skills = {name: self.skill_finder.extract(self.documents[name])[0] for name in self.names}
        self.entity_cache = {}

    def doc_similarity(self, first_name, second_name):
        return float(self.similarity[self.names.index(first_name)][self.names.index(second_name)])

    def text_similarity(self, first_text, second_text):
        vectors = self.vectorizer.transform([first_text, second_text])
        return float(cosine_matrix(vectors[:1], vectors[1:])[0][0])

    def top_keywords(self, name, count=6):
        row = self.keyword_matrix[self.names.index(name)].toarray()[0]
        best = row.argsort()[::-1][:count]
        return [str(self.keyword_terms[i]) for i in best if row[i] > 0]

    def keyword_weights(self, name, count=25):
        row = self.keyword_matrix[self.names.index(name)].toarray()[0]
        best = row.argsort()[::-1][:count]
        return [(str(self.keyword_terms[i]), float(row[i])) for i in best if row[i] > 0]

    def entities(self, name):
        if name not in self.entity_cache:
            self.entity_cache[name] = find_entities(self.documents[name])
        return self.entity_cache[name]

    def word_count(self):
        return sum(len(alpha_words(text)) for text in self.documents.values())


def name_key(file_name):
    stem = os.path.splitext(file_name)[0].lower()
    stem = re.sub(r"(v|ver|version|draft|rev)?\s*\d+", " ", stem)
    return re.sub(r"[_\-\s]+", " ", stem).strip()


def numbers_in_name(file_name):
    found = re.findall(r"\d+", file_name)
    return [int(number) for number in found] if found else [0]


def group_documents(corpus, file_list, min_similarity):
    if len(file_list) < 2:
        return [list(file_list)]
    vectors = corpus.doc_vectors[[corpus.names.index(name) for name in file_list]]
    model = AgglomerativeClustering(n_clusters=None, distance_threshold=1 - min_similarity, metric="cosine", linkage="average")
    labels = model.fit_predict(vectors)
    groups = {}
    for name, label in zip(file_list, labels):
        groups.setdefault(label, []).append(name)
    return list(groups.values())


def detect_roles(corpus, version_similarity=0.35, topic_similarity=0.12):
    def find_files(pattern):
        return [name for name in corpus.names if re.search(pattern, name.lower())]

    job_candidates = find_files(r"job|vacancy|opening|requirement|position")
    resume_files = find_files(r"resume|\bcv\b|_cv|cv_|candidate")
    reference_candidates = find_files(r"reference|gold")
    job_file = job_candidates[0] if job_candidates else None
    reference_file = reference_candidates[0] if reference_candidates else None
    special_files = set(resume_files) | {job_file, reference_file}
    name_groups = {}
    for name in corpus.names:
        if name not in special_files:
            name_groups.setdefault(name_key(name), []).append(name)
    version_groups = []
    for members in name_groups.values():
        if len(members) < 2:
            continue
        members.sort(key=numbers_in_name)
        if min(corpus.doc_similarity(a, b) for a, b in zip(members, members[1:])) >= version_similarity:
            version_groups.append(members)
    older_versions = {name for group in version_groups for name in group[:-1]}
    summary_candidates = [name for name in corpus.names if name not in special_files and name not in older_versions] or corpus.names
    return {
        "job_file": job_file,
        "resume_files": resume_files,
        "reference_file": reference_file,
        "version_groups": version_groups,
        "summary_groups": group_documents(corpus, summary_candidates, topic_similarity),
    }


def find_topics(corpus, max_topics=5, words_per_topic=6):
    if len(corpus.names) == 1:
        words = [word for word, weight in corpus.keyword_weights(corpus.names[0], words_per_topic)]
        table = pd.DataFrame({"document": corpus.names, "main topic": ["Topic 1"], "topic words": [", ".join(words[:4])]})
        return [words], table
    topic_count = max(1, min(max_topics, len(corpus.names) // 2))
    model = NMF(n_components=topic_count, random_state=0, init="nndsvda", max_iter=600)
    weights = model.fit_transform(corpus.keyword_matrix)
    topic_words = [[str(corpus.keyword_terms[i]) for i in component.argsort()[::-1][:words_per_topic]] for component in model.components_]
    main_topics = weights.argmax(axis=1)
    table = pd.DataFrame({
        "document": corpus.names,
        "main topic": [f"Topic {i + 1}" for i in main_topics],
        "topic words": [", ".join(topic_words[i][:4]) for i in main_topics],
    })
    return topic_words, table


def shared_sentences(corpus, version_groups, threshold=0.80):
    def same_group(first, second):
        return any(first in group and second in group for group in version_groups)

    store = corpus.store
    if store.vectors is None:
        return pd.DataFrame(columns=["similarity", "document A", "sentence A", "document B", "sentence B"])
    similarity = store.vectors @ store.vectors.T
    rows = []
    for i, j in np.argwhere(np.triu(similarity, 1) >= threshold):
        first, second = store.sources[i], store.sources[j]
        if first == second or same_group(first, second) or len(store.texts[i].split()) < 5:
            continue
        rows.append({"similarity": round(float(similarity[i][j]), 3), "document A": first, "sentence A": store.texts[i],
                     "document B": second, "sentence B": store.texts[j]})
    table = pd.DataFrame(rows, columns=["similarity", "document A", "sentence A", "document B", "sentence B"])
    return table.sort_values("similarity", ascending=False).reset_index(drop=True)


MATCH_LEVEL = 0.60
CHANGE_LEVEL = 0.40
GAP_PENALTY = -0.6
NUMBERING = r"^\s*((unit|section|chapter|part|article|clause|step|week|module|lesson)\s*)?(\d+(\.\d+)*|[ivx]+)\s*[:.)\-]\s*"


def strip_numbering(sentence):
    return re.sub(NUMBERING, "", sentence, flags=re.IGNORECASE)


def numbers_in(text):
    return set(re.findall(number_pattern, text))


def content_difference(old_sentence, new_sentence):
    old_words = set(get_tokens(old_sentence))
    new_words = set(get_tokens(new_sentence))

    def really_new(word, other_words):
        return not any(difflib.SequenceMatcher(None, word, other).ratio() >= 0.8 for other in other_words)

    added = sorted(word for word in new_words - old_words if really_new(word, old_words))
    removed = sorted(word for word in old_words - new_words if really_new(word, new_words))
    return added, removed, numbers_in(old_sentence) != numbers_in(new_sentence)


def pair_score(similarity):
    if similarity >= MATCH_LEVEL:
        return 2.0
    if similarity >= CHANGE_LEVEL:
        return 1.0
    return -1.0


def needleman_wunsch(old_sentences, new_sentences, vectorizer):
    if not old_sentences or not new_sentences:
        steps = [("REMOVED", s, "", 0.0) for s in old_sentences] + [("ADDED", "", s, 0.0) for s in new_sentences]
        return steps, np.zeros((1, 1))
    similarity = cosine_matrix(vectorizer.transform(old_sentences), vectorizer.transform(new_sentences))
    for i, j in np.argwhere((similarity >= 0.2) & (similarity < MATCH_LEVEL)):
        letters = difflib.SequenceMatcher(None, old_sentences[i].lower(), new_sentences[j].lower())
        if letters.quick_ratio() >= 0.8:
            similarity[i][j] = max(similarity[i][j], letters.ratio() * 0.95)
    rows = len(old_sentences) + 1
    cols = len(new_sentences) + 1
    score = np.zeros((rows, cols))
    for i in range(1, rows):
        score[i][0] = i * GAP_PENALTY
    for j in range(1, cols):
        score[0][j] = j * GAP_PENALTY
    for i in range(1, rows):
        for j in range(1, cols):
            diagonal = score[i - 1][j - 1] + pair_score(similarity[i - 1][j - 1])
            score[i][j] = max(diagonal, score[i - 1][j] + GAP_PENALTY, score[i][j - 1] + GAP_PENALTY)
    steps = []
    i = rows - 1
    j = cols - 1
    while i > 0 or j > 0:
        if i > 0 and j > 0 and score[i][j] == score[i - 1][j - 1] + pair_score(similarity[i - 1][j - 1]):
            value = float(similarity[i - 1][j - 1])
            added, removed, numbers_changed = content_difference(old_sentences[i - 1], new_sentences[j - 1])
            if value >= MATCH_LEVEL and not added and not removed and not numbers_changed:
                steps.append(("SAME", old_sentences[i - 1], new_sentences[j - 1], value))
            elif value >= CHANGE_LEVEL:
                steps.append(("CHANGED", old_sentences[i - 1], new_sentences[j - 1], value))
            else:
                steps.append(("ADDED", "", new_sentences[j - 1], value))
                steps.append(("REMOVED", old_sentences[i - 1], "", value))
            i -= 1
            j -= 1
        elif i > 0 and score[i][j] == score[i - 1][j] + GAP_PENALTY:
            steps.append(("REMOVED", old_sentences[i - 1], "", 0.0))
            i -= 1
        else:
            steps.append(("ADDED", "", new_sentences[j - 1], 0.0))
            j -= 1
    steps.reverse()
    return steps, score


def semantic_relation(steps):
    labels = {step[0] for step in steps}
    if not labels & {"SAME", "CHANGED"}:
        return "No Relation", "the documents share no information"
    old_has_more = "REMOVED" in labels
    new_has_more = "ADDED" in labels
    for label, old_sentence, new_sentence, value in steps:
        if label == "CHANGED":
            added, removed, numbers_changed = content_difference(old_sentence, new_sentence)
            if numbers_changed or (added and removed):
                old_has_more = new_has_more = True
            elif added:
                new_has_more = True
            elif removed:
                old_has_more = True
    if not old_has_more and not new_has_more:
        return "Semantic Equivalence", "both documents carry the same information"
    if not old_has_more:
        return "Semantic Inclusion", "the first document is fully inside the second one"
    if not new_has_more:
        return "Semantic Inclusion", "the second document is fully inside the first one"
    return "Semantic Overlap", "a common core with unique parts on both sides"


def word_key(word):
    return word.strip(".,;:!?()[]'\"").lower()


def word_changes(old_sentence, new_sentence):
    old_words = old_sentence.split()
    new_words = new_sentence.split()
    removed, added = [], []
    for tag, a_start, a_end, b_start, b_end in difflib.SequenceMatcher(None, [word_key(w) for w in old_words], [word_key(w) for w in new_words], autojunk=False).get_opcodes():
        if tag in ("replace", "delete"):
            removed.extend(old_words[a_start:a_end])
        if tag in ("replace", "insert"):
            added.extend(new_words[b_start:b_end])
    return " ".join(removed), " ".join(added)


def word_diff_html(old_sentence, new_sentence):
    old_words = old_sentence.split()
    new_words = new_sentence.split()
    parts = []
    for tag, a_start, a_end, b_start, b_end in difflib.SequenceMatcher(None, [word_key(w) for w in old_words], [word_key(w) for w in new_words], autojunk=False).get_opcodes():
        if tag == "equal":
            parts.append(escape(" ".join(old_words[a_start:a_end])))
        if tag in ("replace", "delete"):
            parts.append("<del>" + escape(" ".join(old_words[a_start:a_end])) + "</del>")
        if tag in ("replace", "insert"):
            parts.append("<ins>" + escape(" ".join(new_words[b_start:b_end])) + "</ins>")
    return " ".join(parts)


def lexical_diff_count(old_lines, new_lines):
    return sum(1 for line in difflib.ndiff(old_lines, new_lines) if line.startswith(("+ ", "- ")))


def vectorizer_for(corpus, *texts):
    known = set(corpus.documents.values())
    if all(text in known for text in texts):
        return corpus.vectorizer
    extra = [sentence for text in texts for sentence in split_sentences(text)]
    return TextVectorizer().fit(corpus.all_sentences + extra + list(texts))


def compare_texts(corpus, old_text, new_text, old_name="first", new_name="second"):
    old_sentences = [strip_numbering(s) for s in split_sentences(old_text)]
    new_sentences = [strip_numbering(s) for s in split_sentences(new_text)]
    vectorizer = vectorizer_for(corpus, old_text, new_text)
    steps, matrix = needleman_wunsch(old_sentences, new_sentences, vectorizer)
    counts = Counter(step[0] for step in steps)
    relation, meaning = semantic_relation(steps)
    in_corpus = old_name in corpus.names and new_name in corpus.names
    old_keywords = set(corpus.top_keywords(old_name, 15)) if in_corpus else set(get_tokens(old_text))
    new_keywords = set(corpus.top_keywords(new_name, 15)) if in_corpus else set(get_tokens(new_text))
    old_skills = set(corpus.skills.get(old_name) or corpus.skill_finder.extract(old_text)[0])
    new_skills = set(corpus.skills.get(new_name) or corpus.skill_finder.extract(new_text)[0])
    return {
        "old": old_name,
        "new": new_name,
        "similarity": round(corpus.doc_similarity(old_name, new_name) if in_corpus else float(cosine_matrix(*[vectorizer.transform([t]) for t in (old_text, new_text)])[0][0]), 3),
        "relation": relation,
        "relation meaning": meaning,
        "steps": steps,
        "alignment score": round(float(matrix[-1][-1]), 2),
        "counts": {label: counts.get(label, 0) for label in ["SAME", "CHANGED", "ADDED", "REMOVED"]},
        "lexical lines flagged": lexical_diff_count(split_sentences(old_text), split_sentences(new_text)),
        "keywords only in old": sorted(old_keywords - new_keywords),
        "keywords only in new": sorted(new_keywords - old_keywords),
        "shared keywords": sorted(old_keywords & new_keywords),
        "skills removed": sorted(old_skills - new_skills),
        "skills added": sorted(new_skills - old_skills),
        "numbers removed": sorted(numbers_in(old_text) - numbers_in(new_text)),
        "numbers added": sorted(numbers_in(new_text) - numbers_in(old_text)),
    }


def compare_documents(corpus, old_name, new_name):
    return compare_texts(corpus, corpus.documents[old_name], corpus.documents[new_name], old_name, new_name)


gender_words = r"\b(he|she|him|her|his|hers|mr|mrs|ms|miss|male|female|man|woman)\b"


def remove_personal_details(text):
    name = find_name_line(text)
    lines = [line for line in text.split("\n") if line.strip()]
    if name:
        lines = [line for line in lines if line.strip() != name]
    elif lines and len(lines[0].split()) <= 4 and not re.search(r"\d|:", lines[0]):
        lines = lines[1:]
    text = "\n".join(lines)
    text = re.sub(r"(?im)^\s*(name|gender|sex|age|date of birth|dob|nationality|religion|caste|marital status|address)\s*:.*$", "", text)
    text = re.sub(r"[\w.+-]+@[\w-]+\.[\w.]+", "", text)
    text = re.sub(r"\+?\d[\d\s-]{8,}\d", "", text)
    return re.sub(gender_words, "", text, flags=re.IGNORECASE)


def requirement_coverage(corpus, job_text, resume_text, threshold=0.30, resume_skills=None):
    requirements = [s for s in split_sentences(job_text) if len(s.split()) >= 6 and "|" not in s]
    lines = split_sentences(resume_text)
    resume_sentences = [s for s in lines if len(s.split()) >= 4] or lines
    if not requirements or not resume_sentences:
        return 0.0, []
    evidence = dict(resume_skills) if resume_skills is not None else corpus.skill_finder.extract(resume_text)[0]
    have = set(evidence)
    similarity = cosine_matrix(corpus.vectorizer.transform(requirements), corpus.vectorizer.transform(resume_sentences))
    rows = []
    for index, requirement in enumerate(requirements):
        best = int(similarity[index].argmax())
        wording = float(similarity[index][best])
        needed = set(corpus.skill_finder.extract(requirement)[0])
        skill_share = len(needed & have) / len(needed) if needed else 0.0
        score = max(wording, skill_share)
        line = resume_sentences[best]
        if skill_share > wording:
            clues = [str(evidence[skill]).split(" (similarity")[0].lower() for skill in needed & have]
            line = next((s for s in lines if any(clue in s.lower() for clue in clues)), line)
        rows.append({"requirement": requirement, "best resume line": line, "skills asked": ", ".join(sorted(needed)),
                     "skills found": ", ".join(sorted(needed & have)), "score": round(score, 3), "covered": score >= threshold})
    return sum(row["covered"] for row in rows) / len(rows), rows


def match_resume(corpus, job_text, resume_text):
    job_skills = corpus.skill_finder.extract(job_text)[0]
    safe_text = remove_personal_details(resume_text)
    resume_skills, rejected = corpus.skill_finder.extract(safe_text)
    needed, have = set(job_skills), set(resume_skills)
    skill_score = len(needed & have) / len(needed) if needed else 0.0
    coverage, coverage_rows = requirement_coverage(corpus, job_text, safe_text, resume_skills=resume_skills)
    text_score = corpus.text_similarity(job_text, safe_text)
    final_score = 0.6 * skill_score + 0.25 * coverage + 0.15 * text_score if needed else 0.6 * coverage + 0.4 * text_score
    return {
        "skill_score": round(skill_score, 3), "coverage": round(coverage, 3), "text_score": round(text_score, 3),
        "final_score": round(final_score, 3), "job_skills": sorted(needed), "matched": sorted(needed & have),
        "missing": sorted(needed - have), "extra": sorted(have - needed), "evidence": resume_skills,
        "rejected": rejected, "coverage_rows": coverage_rows,
    }


swap_pairs = [("he", "she"), ("him", "her"), ("his", "her"), ("mr", "ms"), ("male", "female"), ("man", "woman")]
replacement_names = ["Alex Morgan", "Priya Sharma", "Mohammed Ali", "Chen Wei", "Maria Garcia"]


def make_counterfactual(text, new_name):
    first_line = next((line for line in text.split("\n") if line.strip()), "").strip()
    people = []
    name = find_name_line(text)
    if name:
        people.append(name)
    elif first_line and len(first_line.split()) <= 4 and not re.search(r"\d|:", first_line):
        people.append(first_line)
    name_line = re.search(r"(?im)^\s*name\s*:\s*(.+)$", text)
    if name_line:
        people.append(name_line.group(1).strip())
    for person in set(people):
        if person:
            text = text.replace(person, new_name)
            text = re.sub(rf"\b{re.escape(person.split()[0].lower())}\b", new_name.split()[0].lower(), text)
    for first, second in swap_pairs:
        text = re.sub(rf"\b{first}\b", second, text, flags=re.IGNORECASE)
    return text


def fairness_check(corpus, job_name, resume_names):
    rows = []
    job_text = corpus.documents[job_name]
    for index, name in enumerate(resume_names):
        original = match_resume(corpus, job_text, corpus.documents[name])["final_score"]
        new_name = replacement_names[index % len(replacement_names)]
        swapped = match_resume(corpus, job_text, make_counterfactual(corpus.documents[name], new_name))["final_score"]
        difference = abs(original - swapped)
        rows.append({"resume": name, "original score": original, "name used in test": new_name,
                     "score after swap": swapped, "difference": round(difference, 4), "fair": bool(difference < 0.01)})
    return pd.DataFrame(rows, columns=["resume", "original score", "name used in test", "score after swap", "difference", "fair"])


def textrank_scores(similarity, damping=0.85, rounds=100):
    matrix = similarity.copy()
    np.fill_diagonal(matrix, 0)
    row_sums = matrix.sum(axis=1, keepdims=True)
    row_sums[row_sums == 0] = 1
    matrix = matrix / row_sums
    size = len(matrix)
    scores = np.ones(size) / size
    for _ in range(rounds):
        new_scores = (1 - damping) / size + damping * matrix.T @ scores
        if np.abs(new_scores - scores).sum() < 1e-6:
            break
        scores = new_scores
    return scores


def extract_evidence(corpus, file_list, max_sentences=4, redundancy_limit=0.5):
    sentences, sources = [], []
    for name in file_list:
        for sentence in corpus.sentences[name]:
            tags = [tag for word, tag in nltk.pos_tag(word_tokenize(sentence))]
            has_verb = any(tag.startswith("VB") or tag == "MD" for tag in tags)
            if len(sentence.split()) >= 5 and has_verb:
                sentences.append(sentence)
                sources.append(name)
    if not sentences:
        return []
    vectors = corpus.vectorizer.transform(sentences)
    similarity = cosine_matrix(vectors, vectors)
    rank = textrank_scores(similarity)
    centre = normalize(vectors.mean(axis=0, keepdims=True))
    centrality = (vectors @ centre.T).ravel()
    position_bonus = np.array([1.0 if i == 0 or sources[i] != sources[i - 1] else 0.0 for i in range(len(sentences))])
    scores = 0.6 * rank / rank.max() + 0.3 * centrality / max(centrality.max(), 1e-9) + 0.1 * position_bonus
    chosen = []
    for position in np.argsort(scores)[::-1]:
        if any(similarity[position][other] > redundancy_limit for other in chosen):
            continue
        chosen.append(position)
        if len(chosen) == max_sentences:
            break
    chosen.sort()
    return [{"sentence": sentences[p], "source": sources[p], "score": round(float(scores[p]), 3)} for p in chosen]


short_forms = {
    "in order to": "to", "due to the fact that": "because", "a large number of": "many", "at this point in time": "now",
    "in the event that": "if", "with regard to": "about", "is able to": "can", "are able to": "can",
    "a majority of": "most", "prior to": "before", "is expected to": "will likely", "are expected to": "will likely",
    "is becoming": "is", "at the present time": "now", "for the purpose of": "for",
}
starting_words = ["however", "moreover", "in addition", "also", "furthermore", "therefore", "so", "thus", "finally", "overall"]


def rewrite_sentence(sentence):
    text = re.sub(r"\([^)]*\)", "", sentence)
    for long_form, short_form in short_forms.items():
        text = re.sub(rf"\b{long_form}\b", short_form, text, flags=re.IGNORECASE)
    for word in starting_words:
        if text.lower().startswith(word + ","):
            text = text[len(word) + 1:].strip()
            break
    text = strip_numbering(re.sub(r"\s+", " ", text).strip())
    if text and not text.endswith((".", "!", "?")):
        text = text.rstrip(":;,") + "."
    return text[0].upper() + text[1:] if text else text


def join_sentences(sentences):
    joined = []
    skip_next = False
    for index, sentence in enumerate(sentences):
        if skip_next:
            skip_next = False
            continue
        if index + 1 < len(sentences):
            following = sentences[index + 1]
            shared = set(get_tokens(sentence)) & set(get_tokens(following))
            if len(shared) >= 2 and len(sentence.split()) + len(following.split()) < 35:
                joined.append(sentence.rstrip(".") + ", and " + following[0].lower() + following[1:].rstrip(".") + ".")
                skip_next = True
                continue
        joined.append(sentence)
    return joined


def summarize(corpus, file_list, max_sentences=4):
    evidence = extract_evidence(corpus, file_list, max_sentences=max_sentences)
    rewritten = [rewrite_sentence(item["sentence"]) for item in evidence]
    summary = " ".join(join_sentences(rewritten))
    trace = [{"sentence": rewritten[i], "source": evidence[i]["source"], "score": evidence[i]["score"]} for i in range(len(evidence))]
    return summary, trace


def ngrams(words, size):
    return Counter(tuple(words[i:i + size]) for i in range(len(words) - size + 1))


def f_score(overlap, candidate_total, reference_total):
    precision = overlap / max(candidate_total, 1)
    recall = overlap / max(reference_total, 1)
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0
    return round(precision, 3), round(recall, 3), round(f1, 3)


def rouge_n(candidate, reference, size):
    candidate_grams = ngrams(get_tokens(candidate), size)
    reference_grams = ngrams(get_tokens(reference), size)
    overlap = sum((candidate_grams & reference_grams).values())
    return f_score(overlap, sum(candidate_grams.values()), sum(reference_grams.values()))


def longest_common_subsequence(words_a, words_b):
    table = [[0] * (len(words_b) + 1) for _ in range(len(words_a) + 1)]
    for i in range(1, len(words_a) + 1):
        for j in range(1, len(words_b) + 1):
            if words_a[i - 1] == words_b[j - 1]:
                table[i][j] = table[i - 1][j - 1] + 1
            else:
                table[i][j] = max(table[i - 1][j], table[i][j - 1])
    return table[-1][-1]


def rouge_l(candidate, reference):
    candidate_words = get_tokens(candidate)
    reference_words = get_tokens(reference)
    return f_score(longest_common_subsequence(candidate_words, reference_words), len(candidate_words), len(reference_words))


def vector_score(corpus, candidate, reference):
    candidate_sentences = split_sentences(candidate)
    reference_sentences = split_sentences(reference)
    if not candidate_sentences or not reference_sentences:
        return 0.0, 0.0, 0.0
    similarity = cosine_matrix(corpus.vectorizer.transform(candidate_sentences), corpus.vectorizer.transform(reference_sentences))
    precision = float(similarity.max(axis=1).mean())
    recall = float(similarity.max(axis=0).mean())
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0
    return round(precision, 3), round(recall, 3), round(f1, 3)


def evaluate_summary(corpus, candidate, reference):
    return pd.DataFrame(
        [rouge_n(candidate, reference, 1), rouge_n(candidate, reference, 2), rouge_l(candidate, reference), vector_score(corpus, candidate, reference)],
        index=["ROUGE-1", "ROUGE-2", "ROUGE-L", "Vector similarity"], columns=["precision", "recall", "f1"])


def word_distribution(texts, vocabulary):
    counts = Counter()
    for text in texts:
        counts.update(get_tokens(text))
    values = np.array([counts[word] for word in vocabulary], dtype=float) + 1
    return values / values.sum()


def check_drift(old_texts, new_texts, limit=0.35):
    old_words = set(word for text in old_texts for word in get_tokens(text))
    new_words = [word for text in new_texts for word in get_tokens(text)]
    vocabulary = sorted(old_words | set(new_words))
    if not vocabulary:
        return {"distance": 0.0, "new word ratio": 0.0, "drift": False}
    distance = float(jensenshannon(word_distribution(old_texts, vocabulary), word_distribution(new_texts, vocabulary)))
    unknown_ratio = sum(1 for word in new_words if word not in old_words) / max(len(new_words), 1)
    return {"distance": round(distance, 3), "new word ratio": round(unknown_ratio, 3), "drift": bool(distance > limit or unknown_ratio > 0.5)}


def drift_report(corpus, version_groups):
    drift_rows = [{"check": f"{group[0]} -> {group[-1]}", **check_drift([corpus.documents[group[0]]], [corpus.documents[group[-1]]])}
                  for group in version_groups]
    unusual_rows = []
    for name in corpus.names:
        others = [corpus.documents[other] for other in corpus.names if other != name]
        if others:
            result = check_drift(others, [corpus.documents[name]])
            unusual_rows.append({"document": name, "distance from the rest": result["distance"], "new word ratio": result["new word ratio"]})
    drift_table = pd.DataFrame(drift_rows, columns=["check", "distance", "new word ratio", "drift"])
    unusual_table = pd.DataFrame(unusual_rows, columns=["document", "distance from the rest", "new word ratio"])
    return drift_table, unusual_table.sort_values("distance from the rest", ascending=False).reset_index(drop=True)


def rake_keyphrases(text, top=10, longest=4):
    phrases = []
    for sentence in split_sentences(text):
        pieces = re.findall(r"[a-z][a-z+#]*|[,;:()\[\]!?]", sentence.lower())
        current = []
        for piece in pieces:
            if not piece[0].isalpha() or piece in stop_words:
                if current:
                    phrases.append(current)
                current = []
            else:
                current.append(piece)
        if current:
            phrases.append(current)
    phrases = [phrase for phrase in phrases if len(phrase) <= longest]
    frequency = Counter()
    degree = Counter()
    for phrase in phrases:
        for word in phrase:
            frequency[word] += 1
            degree[word] += len(phrase)
    phrase_scores = {}
    for phrase in phrases:
        key = " ".join(phrase)
        phrase_scores[key] = max(phrase_scores.get(key, 0), sum(degree[word] / frequency[word] for word in phrase))
    best = sorted(phrase_scores.items(), key=lambda item: item[1], reverse=True)[:top]
    return [(phrase, round(score, 2)) for phrase, score in best]


def word_pairs(text, top=10):
    words = [word for word in word_tokenize(text.lower()) if word.isalpha()]
    finder = BigramCollocationFinder.from_words(words)
    finder.apply_word_filter(lambda word: word in stop_words or len(word) < 3)
    if len(words) > 400:
        finder.apply_freq_filter(2)
    scored = finder.score_ngrams(BigramAssocMeasures().likelihood_ratio)[:top]
    return [(" ".join(pair), round(score, 2), finder.ngram_fd[pair]) for pair, score in scored]


document_type_clues = {
    "Resume or CV": "resume curriculum vitae experience skills education project worked built developed email phone linkedin summary internship",
    "Job description": "job description role responsibilities requirements candidate looking hiring apply qualifications preferred required salary position join experience knowledge familiarity nice plus strong excellent",
    "Policy or legal": "policy shall must employee employees rules compliance agreement terms conditions clause leave applies company law allowed",
    "Academic or syllabus": "course unit syllabus students semester exam assessment lecture module credits learning outcomes chapter introduction",
    "News or article": "said reported according year growing world government people million percent new country market expected",
    "Research paper": "abstract method methods results experiment dataset proposed model evaluation conclusion related work accuracy paper study",
    "Technical document": "system software architecture api database server module function requirement design implementation code pipeline",
    "Business or finance": "revenue profit sales cost budget quarter financial market growth investment customers price",
    "Letter or email": "dear regards sincerely thank please request meeting attached hello kindly",
}


def detect_document_type(text):
    words = Counter(stemmer.stem(word) for word in get_tokens(text))
    total = sum(words.values()) or 1
    scores = {}
    for label, clue_text in document_type_clues.items():
        clues = set(stemmer.stem(word) for word in clue_text.split())
        scores[label] = sum(words[clue] for clue in clues) / total
    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    best_label, best_score = ranked[0]
    confidence = best_score / (sum(score for label, score in ranked) or 1)
    return best_label, round(confidence, 2), [(label, round(score, 3)) for label, score in ranked]


def detect_language(text):
    words = set(word for word in word_tokenize(text.lower()) if word.isalpha())
    scores = {}
    for language in stopwords.fileids():
        if language == "hinglish":
            continue
        base = language.split("-")[0]
        scores[base] = max(scores.get(base, 0), len(words & set(stopwords.words(language))))
    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    total = sum(score for language, score in ranked[:3]) or 1
    return ranked[0][0].title(), round(ranked[0][1] / total, 2), [(language.title(), score) for language, score in ranked[:5]]


pos_groups = {"Nouns": "NN", "Verbs": "VB", "Adjectives": "JJ", "Adverbs": "RB", "Pronouns": "PRP", "Numbers": "CD"}


def style_profile(text):
    tokens = [word for word in word_tokenize(text) if any(letter.isalnum() for letter in word)]
    counts = Counter()
    for word, tag in nltk.pos_tag(tokens):
        group = next((name for name, start in pos_groups.items() if tag.startswith(start)), "Others")
        counts[group] += 1
    words = [word for word in tokens if word.isalpha()]
    unique = set(word.lower() for word in words)
    return {
        "pos counts": dict(counts),
        "lexical diversity": round(len(unique) / max(len(words), 1), 3),
        "average word length": round(sum(len(word) for word in words) / max(len(words), 1), 2),
        "long word ratio": round(sum(1 for word in words if len(word) >= 7) / max(len(words), 1), 3),
    }


def readability_scores(text):
    sentences = split_sentences(text)
    words = [word for word in word_tokenize(text) if word.isalpha()]
    if not sentences or not words:
        return {"Flesch reading ease": 0.0, "Flesch-Kincaid grade": 0.0, "Gunning fog": 0.0, "SMOG index": 0.0}
    syllables = [count_syllables(word) for word in words]
    words_per_sentence = len(words) / len(sentences)
    syllables_per_word = sum(syllables) / len(words)
    complex_words = sum(1 for count in syllables if count >= 3)
    return {
        "Flesch reading ease": round(206.835 - 1.015 * words_per_sentence - 84.6 * syllables_per_word, 1),
        "Flesch-Kincaid grade": round(0.39 * words_per_sentence + 11.8 * syllables_per_word - 15.59, 1),
        "Gunning fog": round(0.4 * (words_per_sentence + 100 * complex_words / len(words)), 1),
        "SMOG index": round(1.043 * math.sqrt(complex_words * 30 / len(sentences)) + 3.1291, 1),
    }


def mood_of(score):
    return "Positive" if score > 0.05 else "Negative" if score < -0.05 else "Neutral"


def sentiment_arc(text):
    rows = []
    for index, sentence in enumerate(split_sentences(text), 1):
        score = sentiment_tool.polarity_scores(sentence)["compound"]
        rows.append({"position": index, "sentence": sentence, "score": score, "mood": mood_of(score)})
    return pd.DataFrame(rows, columns=["position", "sentence", "score", "mood"])


question_types = [("how much", "MONEY"), ("cost", "MONEY"), ("price", "MONEY"), ("salary", "MONEY"), ("fee", "MONEY"),
                  ("reimburse", "MONEY"), ("budget", "MONEY"), ("how many", "NUMBER"), ("what percent", "NUMBER"), ("how long", "NUMBER"),
                  ("what year", "DATE"), ("what date", "DATE"), ("which month", "DATE"), ("when", "DATE"), ("who", "PERSON"),
                  ("whom", "PERSON"), ("where", "PLACE"), ("which city", "PLACE"), ("which company", "ORGANIZATION"),
                  ("which organisation", "ORGANIZATION"), ("which organization", "ORGANIZATION"), ("programming language", "SKILL"),
                  ("which skill", "SKILL"), ("what skill", "SKILL"), ("which tool", "SKILL"), ("what tool", "SKILL"),
                  ("framework", "SKILL"), ("technolog", "SKILL")]
number_answer = r"(?:\b\d{1,3}(?:,\d{3})+|\b\d+(?:\.\d+)?)\s?(?:%|percent|days?|years?|months?|hours?|weeks?|people|members|employees|million|billion|lakh|crore)?"
money_answer = r"(?:rs\.?|inr|usd|\$|\u20b9|\u20ac|\u00a3)\s?\d[\d,]*(?:\.\d+)?(?:\s?(?:lakh|crore|k|million|per month|per year|a month|a year))?"


def question_type(question):
    lowered = question.lower()
    for start, kind in question_types:
        if start in lowered:
            return kind
    return "GENERAL"


def short_answer_from(kind, sentence, question=""):
    if kind == "MONEY":
        found = re.findall(money_answer, sentence, flags=re.IGNORECASE)
        return found[0].strip() if found else ""
    if kind == "NUMBER":
        asked = set(get_tokens(question))
        found = [item.strip() for item in re.findall(number_answer, sentence) if item.strip()]
        found = [item for item in found if not re.fullmatch(r"(?:19|20)\d{2}", item)] or found
        with_unit = [item for item in found if any(lemmatizer.lemmatize(word.lower()) in asked for word in item.split()[1:])]
        return (with_unit or [item for item in found if " " in item] or found or [""])[0]
    if kind == "DATE":
        found = re.findall(month_pattern, sentence, flags=re.IGNORECASE)
        return found[0].strip(" .,") if found else ""
    if kind == "SKILL":
        found = {}
        exact_skill_matches(tag_sentence(sentence), found, [])
        return ", ".join(found.keys())
    if kind in ("PERSON", "PLACE", "ORGANIZATION"):
        found = find_entities(sentence)[kind]
        return found.most_common(1)[0][0] if found else ""
    return ""


def answer_question(question, store, top_k=3, only_from=None):
    kind = question_type(question)
    candidates = store.search(question, top_k=max(top_k, 10), only_from=only_from)
    if not candidates:
        return {"question type": kind, "short answer": "", "answer sentence": "", "source": "",
                "score": 0.0, "matched words": [], "other results": []}
    asked = set(get_tokens(question))
    highest = candidates[0]["score"]
    ranked = []
    for item in candidates:
        answer = short_answer_from(kind, item["text"], question) if kind != "GENERAL" else ""
        overlap = len(asked & set(get_tokens(item["text"]))) / max(len(asked), 1)
        usable = bool(answer) and item["score"] >= 0.35 * highest
        ranked.append((usable, item["score"] + 0.1 * overlap, answer, item))
    ranked.sort(key=lambda entry: (entry[0], entry[1]), reverse=True)
    usable, best_score, short_answer, best = ranked[0]
    others = [item for flag, score, answer, item in ranked[1:top_k]]
    matched = sorted(asked & set(get_tokens(best["text"])))
    return {"question type": kind, "short answer": short_answer, "answer sentence": best["text"], "source": best["source"],
            "score": best["score"], "matched words": matched, "other results": others}


def redact_text(text):
    counts = Counter()

    def mask(pattern, label, value, flags=0):
        counts[label] += len(re.findall(pattern, value, flags))
        return re.sub(pattern, f"[{label}]", value, flags=flags)

    text = mask(r"[\w.+-]+@[\w-]+\.[\w.]+", "EMAIL", text)
    text = mask(r"https?://\S+|www\.\S+", "URL", text)
    text = mask(r"\+?\d[\d\s-]{8,}\d", "PHONE", text)
    name = find_name_line(text.replace("[EMAIL]", "@"))
    if name:
        counts["PERSON"] += text.count(name)
        text = text.replace(name, "[PERSON]")
    name_lines = re.findall(r"(?im)^\s*name\s*:\s*(.+)$", text)
    people = set(name.strip() for name in name_lines) | set(find_entities(text)["PERSON"].keys())
    for person in sorted(people, key=len, reverse=True):
        if person and person in text:
            counts["PERSON"] += text.count(person)
            text = text.replace(person, "[PERSON]")
    return text, {label: count for label, count in counts.items() if count}


def shingles(text, size=4):
    words = [word for word in word_tokenize(text.lower()) if word.isalnum()]
    return set(tuple(words[i:i + size]) for i in range(len(words) - size + 1))


def copy_check(text_a, text_b, size=4):
    first, second = shingles(text_a, size), shingles(text_b, size)
    if not first or not second:
        return {"jaccard": 0.0, "A found in B": 0.0, "B found in A": 0.0, "shared phrases": []}
    common = first & second
    return {"jaccard": round(len(common) / len(first | second), 3), "A found in B": round(len(common) / len(first), 3),
            "B found in A": round(len(common) / len(second), 3), "shared phrases": sorted(" ".join(item) for item in common)[:15]}


triple_grammar = nltk.RegexpParser(r"""
    NP: {<DT|PRP\$|CD>?<JJ.*|VBN|VBG>*<NN.*|PRP>+}
    VP: {<MD>?<RB.*>?<VB.*>+<RB.*|RP|IN|TO>?}
""")


pronouns = {"i", "we", "you", "he", "she", "it", "they", "me", "us", "them", "this", "that"}


def find_triples(text, max_sentences=300):
    triples = []
    for sentence in split_sentences(text)[:max_sentences]:
        tree = triple_grammar.parse(nltk.pos_tag(word_tokenize(sentence)))
        chunks = []
        for part in tree:
            if hasattr(part, "label"):
                chunks.append((part.label(), " ".join(word for word, tag in part.leaves())))
            else:
                chunks.append(("O", part[0]))
        for i in range(len(chunks) - 2):
            if chunks[i][0] == "NP" and chunks[i + 1][0] == "VP" and chunks[i + 2][0] == "NP":
                if chunks[i][1].lower() in pronouns or chunks[i + 2][1].lower() in pronouns:
                    continue
                if not re.search(r"[a-z]", chunks[i + 1][1].lower()) or "@" in chunks[i][1] + chunks[i + 2][1]:
                    continue
                triples.append({"subject": chunks[i][1], "relation": chunks[i + 1][1], "object": chunks[i + 2][1], "sentence": sentence})
    return pd.DataFrame(triples, columns=["subject", "relation", "object", "sentence"])


def clean_node(phrase):
    words = [lemmatizer.lemmatize(word) for word in phrase.lower().split() if word not in {"a", "an", "the", "this", "that", "these", "those", "their", "its", "our", "your"}]
    return " ".join(words) or phrase.lower()


def build_graph(triples):
    graph = nx.DiGraph()
    for row in triples.itertuples():
        graph.add_edge(clean_node(row.subject), clean_node(row.object), label=row.relation.lower())
    return graph


wordnet_types = {"n": "noun", "v": "verb", "a": "adjective", "s": "adjective", "r": "adverb"}


def word_meaning(word, limit=4):
    rows = []
    for synset in wordnet.synsets(word.strip().replace(" ", "_"))[:limit]:
        lemmas = synset.lemmas()
        rows.append({
            "type": wordnet_types.get(synset.pos(), synset.pos()),
            "meaning": synset.definition(),
            "synonyms": ", ".join(sorted({lemma.name().replace("_", " ") for lemma in lemmas})[:6]),
            "opposites": ", ".join(sorted({opposite.name().replace("_", " ") for lemma in lemmas for opposite in lemma.antonyms()})),
            "broader idea": ", ".join(hyper.lemmas()[0].name().replace("_", " ") for hyper in synset.hypernyms()[:2]),
            "example": synset.examples()[0] if synset.examples() else "",
        })
    return pd.DataFrame(rows, columns=["type", "meaning", "synonyms", "opposites", "broader idea", "example"])


tag_meanings = {
    "NN": "noun", "NNS": "plural noun", "NNP": "proper noun", "NNPS": "plural proper noun", "VB": "verb", "VBD": "past tense verb",
    "VBG": "verb ending in ing", "VBN": "past participle", "VBP": "present verb", "VBZ": "present verb", "JJ": "adjective",
    "JJR": "comparing adjective", "JJS": "most adjective", "RB": "adverb", "RBR": "comparing adverb", "PRP": "pronoun",
    "PRP$": "possessive pronoun", "DT": "determiner", "IN": "preposition", "CC": "joining word", "CD": "number", "MD": "modal verb",
    "TO": "to", "UH": "interjection", "WP": "question word", "WDT": "question word", "WRB": "question word", "RP": "particle",
    "EX": "there", "POS": "possessive ending",
}


def wordnet_tag(tag):
    if tag.startswith("J"):
        return "a"
    if tag.startswith("V"):
        return "v"
    if tag.startswith("R"):
        return "r"
    return "n"


def nlp_pipeline(sentence):
    tagged = nltk.pos_tag(word_tokenize(sentence))
    tree = entity_chunker.parse(tagged)
    entity_labels = []
    for part in tree:
        if hasattr(part, "label"):
            entity_labels.extend([part.label()] * len(part.leaves()))
        else:
            entity_labels.append("")
    rows = []
    for (word, tag), entity in zip(tagged, entity_labels):
        rows.append({"token": word, "lowercase": word.lower(), "stopword": "yes" if word.lower() in stop_words else "no",
                     "stem": stemmer.stem(word.lower()), "lemma": lemmatizer.lemmatize(word.lower(), wordnet_tag(tag)),
                     "POS tag": tag, "meaning": tag_meanings.get(tag, "punctuation or symbol"), "entity": entity})
    return pd.DataFrame(rows)


def sentence_map(vectorizer, sentence_items):
    if len(sentence_items) < 3:
        return pd.DataFrame(columns=["x", "y", "document", "sentence"])
    vectors = vectorizer.transform([sentence for source, sentence in sentence_items])
    points = PCA(n_components=2, random_state=0).fit_transform(vectors)
    return pd.DataFrame({"x": points[:, 0], "y": points[:, 1], "document": [source for source, sentence in sentence_items],
                         "sentence": [sentence for source, sentence in sentence_items]})


def word_frequency(text, top=20):
    return Counter(get_tokens(text)).most_common(top)


def zipf_table(text):
    counts = Counter(get_tokens(text)).most_common()
    return pd.DataFrame({"rank": range(1, len(counts) + 1), "word": [word for word, count in counts], "count": [count for word, count in counts]})


def overview_table(corpus):
    rows = []
    for name in corpus.names:
        text = corpus.documents[name]
        score = readability(text)
        mood_score, mood = sentiment(text)
        doc_type, type_confidence, type_scores = detect_document_type(text)
        language, language_confidence, language_scores = detect_language(text)
        words = alpha_words(text)
        rows.append({
            "document": name,
            "type": doc_type,
            "language": language,
            "words": len(words),
            "sentences": len(corpus.sentences[name]),
            "unique words": len(set(word.lower() for word in words)),
            "readability": score,
            "level": reading_level(score),
            "sentiment": mood_score,
            "mood": mood,
            "top keywords": ", ".join(corpus.top_keywords(name, 5)),
        })
    return pd.DataFrame(rows)


def run_self_tests(corpus):
    test_lines = ["Intro to the course.", "Tokenization basics.", "Language models and smoothing.", "Word embeddings such as GloVe.",
                  "Employees get 12 days of leave.", "Employees get 15 days of leave.",
                  "Text preprocessing including tokenization and stopword removal.", "Text preprocesing includng tokenizaton and stopword remval."]
    vectorizer = TextVectorizer().fit(corpus.all_sentences + test_lines)
    finder = corpus.skill_finder

    def test_tokens():
        assert get_tokens("The cats are running") == ["cat", "running"]

    def test_sentence_split_joins_broken_lines():
        assert len(split_sentences("This is a long line that was broken by the PDF reader in the middle of the\nsentence and it continues here.")) == 1

    def test_polish_verb_rejected():
        assert "Polish Language" not in finder.extract("We hand-polish the UI before release.")[0]

    def test_frontend_scripting_is_javascript():
        assert "JavaScript" in finder.extract("Comfortable with frontend scripting.")[0]

    def test_alignment_same_text():
        lines = ["Intro to the course.", "Tokenization basics.", "Language models and smoothing."]
        assert all(step[0] == "SAME" for step in needleman_wunsch(lines, lines, vectorizer)[0])

    def test_alignment_finds_added_line():
        old = ["Intro to the course.", "Language models and smoothing."]
        new = ["Intro to the course.", "Word embeddings such as GloVe.", "Language models and smoothing."]
        assert [step[0] for step in needleman_wunsch(old, new, vectorizer)[0]] == ["SAME", "ADDED", "SAME"]

    def test_number_change_is_not_same():
        assert needleman_wunsch(["Employees get 12 days of leave."], ["Employees get 15 days of leave."], vectorizer)[0][0][0] == "CHANGED"

    def test_spelling_errors_still_same():
        steps = needleman_wunsch(["Text preprocessing including tokenization and stopword removal."],
                                 ["Text preprocesing includng tokenizaton and stopword remval."], vectorizer)[0]
        assert steps[0][0] == "SAME"

    def test_rouge_perfect_match():
        assert rouge_n("the cat sat on the mat", "the cat sat on the mat", 1)[2] == 1.0

    def test_language_detection():
        assert detect_language("Le chat est sur la table et il dort avec le chien.")[0] == "French"

    def test_redaction_hides_email():
        assert "@" not in redact_text("Contact me at someone@example.com today.")[0]

    def test_question_type():
        assert question_type("How many days of leave?") == "NUMBER"

    tests = [test_tokens, test_sentence_split_joins_broken_lines, test_polish_verb_rejected, test_frontend_scripting_is_javascript,
             test_alignment_same_text, test_alignment_finds_added_line, test_number_change_is_not_same, test_spelling_errors_still_same,
             test_rouge_perfect_match, test_language_detection, test_redaction_hides_email, test_question_type]
    rows = []
    for test in tests:
        start = time.perf_counter()
        try:
            test()
            result = "PASSED"
        except AssertionError:
            result = "FAILED"
        rows.append({"test": test.__name__.replace("test_", "").replace("_", " "), "result": result,
                     "time ms": round((time.perf_counter() - start) * 1000, 2)})
    return pd.DataFrame(rows)


def measure_time(function, *arguments, rounds=3):
    times = []
    for _ in range(rounds):
        start = time.perf_counter()
        function(*arguments)
        times.append(time.perf_counter() - start)
    return round(min(times) * 1000, 2), round(sum(times) / len(times) * 1000, 2)


def run_benchmark(corpus, roles):
    first = corpus.names[0]
    jobs = [
        ("vector search", corpus.store.search, ("main idea of the document",)),
        ("skill extraction", corpus.skill_finder.extract, (corpus.documents[first],)),
        ("summary", summarize, (corpus, [first])),
        ("keyphrases", rake_keyphrases, (corpus.documents[first],)),
    ]
    if roles["version_groups"]:
        group = roles["version_groups"][0]
        jobs.append(("version comparison", compare_documents, (corpus, group[0], group[1])))
    if roles["job_file"] and roles["resume_files"]:
        jobs.append(("resume match", match_resume, (corpus, corpus.documents[roles["job_file"]], corpus.documents[roles["resume_files"][0]])))
    rows = []
    for label, function, arguments in jobs:
        fastest, average = measure_time(function, *arguments)
        rows.append({"task": label, "fastest ms": fastest, "average ms": average})
    return pd.DataFrame(rows)


def heatmap_png(corpus):
    size = (max(7, len(corpus.names) * 0.75), max(6, len(corpus.names) * 0.65))
    figure, axis = plt.subplots(figsize=size)
    picture = axis.imshow(corpus.similarity, cmap="Purples", vmin=0, vmax=1)
    axis.set_xticks(range(len(corpus.names)))
    axis.set_yticks(range(len(corpus.names)))
    axis.set_xticklabels(corpus.names, rotation=60, ha="right", fontsize=8)
    axis.set_yticklabels(corpus.names, fontsize=8)
    for row in range(len(corpus.names)):
        for col in range(len(corpus.names)):
            value = corpus.similarity[row][col]
            axis.text(col, row, f"{value:.2f}", ha="center", va="center", fontsize=7, color="white" if value > 0.6 else "black")
    figure.colorbar(picture)
    plt.tight_layout()
    buffer = io.BytesIO()
    figure.savefig(buffer, format="png", dpi=150)
    plt.close(figure)
    buffer.seek(0)
    return buffer, size


def build_report(corpus, roles, summary_sentences=4):
    styles = getSampleStyleSheet()
    heading = ParagraphStyle("heading", parent=styles["Heading2"], textColor=colors.HexColor("#4338ca"))
    small_heading = styles["Heading3"]
    body = ParagraphStyle("body", parent=styles["BodyText"], fontSize=9, leading=12)
    summary_style = ParagraphStyle("summary", parent=styles["BodyText"], fontSize=10.5, leading=21)
    added_style = ParagraphStyle("added", parent=body, backColor=colors.HexColor("#d9f2d9"), borderPadding=3, spaceAfter=5)
    removed_style = ParagraphStyle("removed", parent=body, backColor=colors.HexColor("#f8d7d7"), borderPadding=3, spaceAfter=5)
    changed_style = ParagraphStyle("changed", parent=body, backColor=colors.HexColor("#fff1cc"), borderPadding=3, spaceAfter=5)
    same_style = ParagraphStyle("same", parent=body, textColor=colors.grey, spaceAfter=5)
    width = A4[0] - 80

    def cell(value):
        return Paragraph(escape(str(value)), body)

    def table(frame, widths=None):
        rows = [[cell(column) for column in frame.columns]] + [[cell(value) for value in values] for values in frame.values.tolist()]
        result = Table(rows, colWidths=widths or [width / len(frame.columns)] * len(frame.columns), repeatRows=1)
        result.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e0e7ff")),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#c7c9d9")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f6fb")]),
        ]))
        return result

    buffer = io.BytesIO()
    document = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=40, rightMargin=40, topMargin=40, bottomMargin=40)
    overview = overview_table(corpus)
    story = [Paragraph("Multi Document NLP Scanner Report", styles["Title"]),
             Paragraph(escape(f"Created on {time.strftime('%d %B %Y, %H:%M')} for {len(corpus.names)} documents"), body), Spacer(1, 10),
             Paragraph("1. Document overview", heading),
             table(overview[["document", "type", "words", "readability", "level", "mood", "top keywords"]], [95, 75, 40, 50, 45, 45, width - 350])]
    image, size = heatmap_png(corpus)
    story += [Spacer(1, 8), Paragraph("Similarity between documents", small_heading),
              PdfImage(image, width=width * 0.8, height=width * 0.8 * size[1] / size[0]), PageBreak()]

    story.append(Paragraph("2. Entities, skills and key phrases", heading))
    rows = []
    for name in corpus.names:
        parts = [f"{label}: {', '.join(item for item, count in counter.most_common(4))}" for label, counter in corpus.entities(name).items() if counter]
        rows.append({"document": name, "entities": "; ".join(parts) or "none", "skills": ", ".join(corpus.skills[name]) or "none",
                     "key phrases": ", ".join(phrase for phrase, score in rake_keyphrases(corpus.documents[name], 4))})
    story.append(table(pd.DataFrame(rows), [85, width - 335, 120, 130]))

    if roles["job_file"] and roles["resume_files"]:
        story += [PageBreak(), Paragraph("3. Resume and job matching", heading)]
        job_text = corpus.documents[roles["job_file"]]
        results = {name: match_resume(corpus, job_text, corpus.documents[name]) for name in roles["resume_files"]}
        ordered = sorted(results, key=lambda name: results[name]["final_score"], reverse=True)
        frame = pd.DataFrame([{"rank": i + 1, "resume": name, "final": results[name]["final_score"], "skills": results[name]["skill_score"],
                               "coverage": results[name]["coverage"], "matched": ", ".join(results[name]["matched"]) or "none",
                               "missing": ", ".join(results[name]["missing"]) or "none"} for i, name in enumerate(ordered)])
        story.append(table(frame, [30, 70, 35, 35, 50, (width - 220) / 2, (width - 220) / 2]))
        story += [Spacer(1, 6), Paragraph("Fairness check", small_heading), table(fairness_check(corpus, roles["job_file"], roles["resume_files"]))]

    if roles["version_groups"]:
        story += [PageBreak(), Paragraph("4. Semantic version comparison", heading),
                  Paragraph("Green means added, red means removed, yellow means changed and grey means the same.", body)]
        for group in roles["version_groups"]:
            for old_name, new_name in zip(group, group[1:]):
                result = compare_documents(corpus, old_name, new_name)
                story.append(Paragraph(escape(f"{old_name} to {new_name}"), small_heading))
                story.append(Paragraph(escape(f"Similarity {result['similarity']}. {result['relation']}: {result['relation meaning']}. "
                                              f"Changes {result['counts']}. A normal line diff flags {result['lexical lines flagged']} lines."), body))
                for label, old_sentence, new_sentence, value in result["steps"]:
                    if label == "ADDED":
                        story.append(Paragraph("<b>ADDED:</b> " + escape(new_sentence), added_style))
                    elif label == "REMOVED":
                        story.append(Paragraph("<b>REMOVED:</b> " + escape(old_sentence), removed_style))
                    elif label == "CHANGED":
                        story.append(Paragraph(f"<b>CHANGED ({value:.2f}):</b> {escape(old_sentence)}<br/><b>NOW:</b> {escape(new_sentence)}", changed_style))
                    else:
                        story.append(Paragraph("SAME: " + escape(new_sentence), same_style))

    story += [PageBreak(), Paragraph("5. Summaries", heading)]
    for group in roles["summary_groups"]:
        summary, trace = summarize(corpus, group, summary_sentences)
        story += [Paragraph(escape("Documents: " + ", ".join(group)), small_heading), Paragraph(escape(summary), summary_style)]
        if trace:
            story.append(table(pd.DataFrame(trace)[["sentence", "source"]], [width - 110, 110]))
        story.append(Spacer(1, 6))

    drift_table, unusual_table = drift_report(corpus, roles["version_groups"])
    story += [PageBreak(), Paragraph("6. Drift and quality checks", heading)]
    if not drift_table.empty:
        story += [table(drift_table, [width - 210, 70, 80, 60]), Spacer(1, 6)]
    story += [table(unusual_table), Spacer(1, 6), table(run_self_tests(corpus))]
    document.build(story)
    return buffer.getvalue()
