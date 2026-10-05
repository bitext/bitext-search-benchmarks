"""MIRACL English input acquisition and deterministic test-fixture selection.

This module deliberately contains benchmark-dataset knowledge only.  The
Elasticsearch and TREC machinery in ``benchmark.py`` accepts documents, topics,
and qrels without depending on MIRACL's storage layout.
"""

from __future__ import annotations

import csv
import gzip
import itertools
import json
import shutil
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "scripts/config/benchmark.json").read_text(encoding="utf-8"))
DATA_DIRECTORY = ROOT / "data" / "miracl" / "en"


def dataset_url(repository: str, revision: str, relative_path: str) -> str:
    return f"https://huggingface.co/datasets/{repository}/resolve/{revision}/{relative_path}"


def download(url: str, destination: Path) -> None:
    """Cache a revision-pinned public input atomically under generated data/."""
    if destination.is_file():
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".partial")
    request = urllib.request.Request(url, headers={"User-Agent": "bitext-search-benchmarks/1.0"})
    with urllib.request.urlopen(request, timeout=120) as response, partial.open("wb") as handle:
        shutil.copyfileobj(response, handle)
    partial.replace(destination)


def load_topics_and_qrels() -> tuple[list[tuple[str, str]], dict[str, dict[str, int]]]:
    """Acquire and validate the revision-pinned MIRACL English development set."""
    miracl = CONFIG["miracl"]
    raw_directory = DATA_DIRECTORY / "raw"
    topics_path = raw_directory / "topics_dev.tsv"
    qrels_path = raw_directory / "qrels_dev.tsv"
    benchmark_repository = miracl["benchmark_repository"]
    benchmark_revision = miracl["benchmark_revision"]
    download(
        dataset_url(benchmark_repository, benchmark_revision, "miracl-v1.0-en/topics/topics.miracl-v1.0-en-dev.tsv"),
        topics_path,
    )
    download(
        dataset_url(benchmark_repository, benchmark_revision, "miracl-v1.0-en/qrels/qrels.miracl-v1.0-en-dev.tsv"),
        qrels_path,
    )
    with topics_path.open(encoding="utf-8") as handle:
        topics = [(row[0], row[1]) for row in csv.reader(handle, delimiter="\t") if len(row) >= 2]
    qrels: dict[str, dict[str, int]] = {}
    for line in qrels_path.read_text(encoding="utf-8").splitlines():
        qid, _unused, docid, relevance = line.split()
        qrels.setdefault(qid, {})[docid] = int(relevance)
    expected = miracl["expected"]
    if len(topics) != expected["queries"] or sum(map(len, qrels.values())) != expected["qrels"]:
        raise ValueError("MIRACL topic/qrel validation failed")
    return topics, qrels


def corpus_shard_documents(number: int):
    """Yield one revision-pinned MIRACL corpus shard in stored source order."""
    miracl = CONFIG["miracl"]
    shard_name = f"docs-{number}.jsonl.gz"
    shard_path = DATA_DIRECTORY / "raw" / "corpus" / shard_name
    download(
        dataset_url(miracl["corpus_repository"], miracl["corpus_revision"], f"miracl-corpus-v1.0-en/{shard_name}"),
        shard_path,
    )
    with gzip.open(shard_path, "rt", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def corpus_documents(*, limit: int | None = None):
    """Yield MIRACL passages in canonical shard order."""
    emitted = 0
    for shard_number in range(66):
        for document in corpus_shard_documents(shard_number):
            yield document
            emitted += 1
            if limit is not None and emitted >= limit:
                return


def positive_qrel_documents(qrels: dict[str, dict[str, int]], qid: str) -> set[str]:
    """Return original positively judged documents for a development topic."""
    return {docid for docid, relevance in qrels.get(qid, {}).items() if relevance > 0}


def select_test_topics(
    topics: list[tuple[str, str]],
    qrels: dict[str, dict[str, int]],
    available_documents: set[str],
) -> tuple[list[tuple[str, str]], set[str]]:
    """Select qrels-bearing topics using MIRACL data only, never retrieval output.

    Restricting the fixture to its small initial shard set keeps a first run
    compact. Topic order remains canonical, and every selected positive
    passage must fit in the configured corpus before deterministic distractors
    are added.
    """
    selected_topics: list[tuple[str, str]] = []
    selected_documents: set[str] = set()
    topic_limit = int(CONFIG["miracl"]["test_queries"])
    corpus_limit = int(CONFIG["miracl"]["test_documents"])
    for topic in topics:
        positives = positive_qrel_documents(qrels, topic[0])
        combined_documents = selected_documents | positives
        if positives and positives <= available_documents and len(combined_documents) <= corpus_limit:
            selected_topics.append(topic)
            selected_documents = combined_documents
        if len(selected_topics) == topic_limit:
            return selected_topics, selected_documents
    raise RuntimeError("test corpus shards cannot provide the configured qrels-driven test fixture")


def build_test_corpus(candidates, selected_documents: set[str]) -> list[dict]:
    """Keep judged passages and fill the configured fixture in source order."""
    target_size = int(CONFIG["miracl"]["test_documents"])
    if len(selected_documents) > target_size:
        raise ValueError("selected positive judgments exceed the test corpus size")
    positives: list[dict] = []
    distractors: list[dict] = []
    for document in candidates:
        if str(document["docid"]) in selected_documents:
            positives.append(document)
        elif len(distractors) < target_size - len(selected_documents):
            distractors.append(document)
    if {str(document["docid"]) for document in positives} != selected_documents:
        raise ValueError("test corpus shard did not contain every selected positive judgment")
    corpus = positives + distractors
    if len(corpus) != target_size or len({str(document["docid"]) for document in corpus}) != target_size:
        raise ValueError("test corpus must contain exactly the configured number of unique documents")
    return corpus


def prepare_test_data() -> tuple[list[dict], list[tuple[str, str]], dict[str, dict[str, int]]]:
    """Build the deterministic 50-query / 500-passage qrels-bearing fixture."""
    topics, qrels = load_topics_and_qrels()
    available_documents = {str(document["docid"]) for document in test_corpus_documents()}
    test_topics, selected_documents = select_test_topics(topics, qrels, available_documents)
    corpus = build_test_corpus(test_corpus_documents(), selected_documents)
    return corpus, test_topics, qrels


def test_corpus_documents():
    """Yield the first two public corpus shards used by the compact test fixture."""
    return itertools.chain(corpus_shard_documents(0), corpus_shard_documents(1))


def qrels_for_topics(topics: list[tuple[str, str]], result_directory: Path) -> Path:
    """Return full qrels or a generated qrel subset for the test fixture."""
    source = DATA_DIRECTORY / "raw" / "qrels_dev.tsv"
    selected_ids = {qid for qid, _ in topics}
    if len(selected_ids) == CONFIG["miracl"]["expected"]["queries"]:
        return source
    selected_lines = [
        line for line in source.read_text(encoding="utf-8").splitlines() if line.split()[0] in selected_ids
    ]
    path = result_directory / "provenance" / "scoring-qrels.tsv"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(selected_lines) + "\n", encoding="utf-8")
    return path
