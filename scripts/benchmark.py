#!/usr/bin/env python3
"""Deterministic MIRACL English lexical-search benchmark.

``test`` exercises the real acquisition, indexing, retrieval, official scoring,
and reporting pipeline on a deterministic subset. ``full`` runs the complete
corpus. Both retrieve 100 documents per query; score ties sort by document ID.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile
from pathlib import Path
from urllib.error import HTTPError

try:  # Support both ``python scripts/benchmark.py`` and package imports in tests.
    from scripts import miracl
except ModuleNotFoundError:
    import miracl

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "scripts/config/benchmark.json").read_text(encoding="utf-8"))
RESULTS = ROOT / "results"
ARMS = {
    "standard": "standard",
    "elastic-english": "english",
    "bitext-english": CONFIG["plugin"]["analyzer"],
}
METRICS = ("nDCG@10", "Recall@10", "Recall@100", "Precision@10", "F1@10", "MRR@10")
RETRIEVAL_DEPTH = 100
MRR_CUTOFF = 10
TREC_EVAL_MEASURES = ("ndcg_cut.10", "P.10", "recall.10,100")
_TREC_EVAL_BINARY: Path | None = None


def status(message: str) -> None:
    """Print one concise, user-facing benchmark stage."""
    print(message, flush=True)


def sha256(path: Path) -> str:
    """Return an observed digest for generated provenance, never a config pin."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def plugin_archive() -> Path:
    """Find the one distributable plugin archive without hard-coded filename/hash."""
    archives = sorted((ROOT / "plugin").glob("*.zip"))
    if len(archives) != 1:
        raise RuntimeError(f"plugin/ must contain exactly one ZIP archive, found {len(archives)}")
    return archives[0]


def plugin_version() -> str:
    """Read the bundled plugin version for progress output only."""
    with zipfile.ZipFile(plugin_archive()) as archive:
        descriptor = archive.read("stable-plugin-descriptor.properties").decode("utf-8")
    return next(
        line.removeprefix("version=")
        for line in descriptor.splitlines()
        if line.startswith("version=")
    )


# Compatibility exports keep focused tests and downstream exploratory use simple;
# the implementations live in the MIRACL-only module.
positive_qrel_documents = miracl.positive_qrel_documents
select_test_topics = miracl.select_test_topics
build_test_corpus = miracl.build_test_corpus


def arm_label(arm: str) -> str:
    """Return the concise treatment name used in user-facing progress output."""
    return {
        "standard": "Elasticsearch Standard",
        "elastic-english": "Elasticsearch English",
        "bitext-english": "Bitext English Analyzer",
    }[arm]


def es_request(method: str, endpoint: str, path: str, body: object | None = None) -> dict:
    payload = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(endpoint + path, data=payload, method=method)
    if payload is not None:
        request.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(request, timeout=180) as response:
        return json.loads(response.read() or b"{}")


def es_endpoint() -> str:
    return "http://localhost:" + os.environ.get("MIRACL_ES_PORT", "9200")


def prepare_es_data_directory() -> Path:
    """Resolve and validate the generated host directory mounted into Elasticsearch."""
    requested = Path(os.environ.get("MIRACL_ES_DATA_DIR", ROOT / "data" / "elasticsearch"))
    data_directory = requested if requested.is_absolute() else (ROOT / requested)
    data_directory = data_directory.resolve()
    data_directory.mkdir(parents=True, exist_ok=True)
    if not data_directory.is_dir() or not os.access(data_directory, os.W_OK | os.X_OK):
        raise RuntimeError(
            f"Elasticsearch data directory is not writable: {data_directory}. "
            "Set MIRACL_ES_DATA_DIR to a writable host directory."
        )
    os.environ["MIRACL_ES_DATA_DIR"] = str(data_directory)
    return data_directory


def require_docker_daemon() -> None:
    """Fail clearly before mount validation when Docker itself is unavailable."""
    try:
        completed = subprocess.run(["docker", "info"], text=True, capture_output=True)
    except FileNotFoundError as error:
        raise RuntimeError("Docker is not installed. Install Docker and retry.") from error
    if completed.returncode != 0:
        raise RuntimeError(
            "Docker is installed, but the Docker daemon is not running. "
            "Start Docker Desktop (or the Docker service) and retry."
        )


def verify_es_data_directory(data_directory: Path) -> None:
    """Check that Elasticsearch's runtime UID can write the bind mount."""
    image = f"docker.elastic.co/elasticsearch/elasticsearch:{CONFIG['elasticsearch_version']}"
    command = [
        "docker", "run", "--rm", "--user", "1000:0", "--mount",
        f"type=bind,src={data_directory},dst=/usr/share/elasticsearch/data",
        "--entrypoint", "/bin/sh", image, "-c", "test -w /usr/share/elasticsearch/data",
    ]
    completed = subprocess.run(command, text=True, capture_output=True)
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        if "connect to the docker API" in detail or "docker daemon is not running" in detail:
            raise RuntimeError(
                "Docker is installed, but the Docker daemon is not running. "
                "Start Docker Desktop (or the Docker service) and retry."
            )
        raise RuntimeError(
            f"Elasticsearch runtime user cannot write {data_directory}. "
            "Choose MIRACL_ES_DATA_DIR owned or writable by UID 1000 (without chmod 777). "
            f"Docker reported: {detail}"
        )


def start_elasticsearch(*, full: bool) -> str:
    """Build Elasticsearch with the discovered plugin and verify it is loaded."""
    # The analyzer's lexical resources need more heap than Elasticsearch's
    # image default for repeatable three-arm test indexing. Users can override
    # either default through MIRACL_ES_JAVA_OPTS.
    status(f"Starting Elasticsearch {CONFIG['elasticsearch_version']}...")
    os.environ.setdefault("MIRACL_ES_JAVA_OPTS", "-Xms24g -Xmx24g" if full else "-Xms2g -Xmx2g")
    require_docker_daemon()
    verify_es_data_directory(prepare_es_data_directory())
    run_captured(
        ["docker", "compose", "-f", "scripts/docker/compose.yml", "up", "--build", "-d"],
        "build and start Elasticsearch",
        cwd=ROOT,
    )
    endpoint, expected_version = es_endpoint(), CONFIG["elasticsearch_version"]
    for _ in range(60):
        try:
            if es_request("GET", endpoint, "/").get("version", {}).get("number") == expected_version:
                break
        except Exception:
            pass
        time.sleep(2)
    else:
        raise RuntimeError(f"Elasticsearch did not become ready as {expected_version}")
    nodes = es_request("GET", endpoint, "/_nodes/plugins")
    names = {item["name"] for node in nodes["nodes"].values() for item in node.get("plugins", [])}
    if CONFIG["plugin"]["name"] not in names:
        raise RuntimeError("Bitext Java plugin was not loaded")
    status("Elasticsearch is ready.")
    return endpoint


def bitext_analysis() -> dict:
    """Use the analyzer's minimal public configuration."""
    analyzer = CONFIG["plugin"]["analyzer"]
    return {
        "analysis": {
            "analyzer": {analyzer: {"type": "bitext_java_english"}},
        }
    }


def index_body(analyzer: str) -> dict:
    """Mappings shared by every arm; the analyzer is the treatment variable."""
    settings = {
        "number_of_shards": 1,
        "number_of_replicas": 0,
        "similarity": {"default": {"type": "BM25", **CONFIG["bm25"]}},
    }
    if analyzer == CONFIG["plugin"]["analyzer"]:
        settings.update(bitext_analysis())
    text_field = {"type": "text", "analyzer": analyzer, "search_analyzer": analyzer}
    return {
        "settings": settings,
        "mappings": {
            "properties": {
                "docid": {"type": "keyword"},
                "title": text_field,
                "text": text_field,
                "contents": text_field,
            }
        },
    }


def bulk_index(endpoint: str, index: str, documents: list[dict], *, allow_conflicts: bool = False) -> int:
    """Create documents, accepting duplicates only while resuming a full index."""
    lines: list[str] = []
    for document in documents:
        title, text = (document.get("title") or "").strip(), (document.get("text") or "").strip()
        lines.extend((json.dumps({"create": {"_index": index, "_id": str(document["docid"])} }),
            json.dumps({"docid": str(document["docid"]), "title": title, "text": text,
                "contents": (title + "\n" + text).strip()}, ensure_ascii=False)))
    request = urllib.request.Request(endpoint + "/_bulk", data=("\n".join(lines) + "\n").encode(), method="POST",
        headers={"Content-Type": "application/x-ndjson"})
    with urllib.request.urlopen(request, timeout=600) as response:
        outcome = json.loads(response.read())
    created = 0
    for item in outcome.get("items", []):
        result = item.get("create", {})
        if result.get("status") == 201:
            created += 1
        elif not (allow_conflicts and result.get("status") == 409):
            raise RuntimeError(f"bulk indexing failure: {result}")
    if len(outcome.get("items", [])) != len(documents):
        raise RuntimeError("bulk response item-count mismatch")
    return created


def write_trec_run(endpoint: str, index: str, analyzer: str, topics: list[tuple[str, str]], output: Path) -> None:
    """Write canonical six-column TREC output at depth 100, ties by docid."""
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as handle:
        for qid, query in topics:
            body = {
                "size": RETRIEVAL_DEPTH,
                "track_scores": True,
                "query": {
                    "match": {
                        "contents": {"query": query, "operator": "or", "analyzer": analyzer}
                    }
                },
                "sort": [{"_score": "desc"}, {"docid": "asc"}],
            }
            hits = es_request("POST", endpoint, f"/{index}/_search", body)["hits"]["hits"]
            for rank, hit in enumerate(hits, 1):
                handle.write(f"{qid} Q0 {hit['_id']} {rank} {float(hit['_score']):.6f} {index}\n")


def trec_eval_source_directory() -> Path:
    """Return the generated, revision-namespaced checkout location for trec_eval."""
    return ROOT / "data" / "tools" / "trec_eval" / CONFIG["trec_eval"]["revision"] / "source"


def trec_eval_binary() -> Path:
    """Build exactly the pinned official NIST scorer under generated data/tools/."""
    global _TREC_EVAL_BINARY
    if _TREC_EVAL_BINARY is not None:
        return _TREC_EVAL_BINARY
    pinned = CONFIG["trec_eval"]
    source = trec_eval_source_directory()
    binary = source / "trec_eval"
    if source.exists():
        if subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source, text=True).strip() != pinned["revision"]:
            raise RuntimeError("cached trec_eval revision mismatch")
        status(f"Using cached NIST trec_eval {pinned['version']}")
    else:
        source.parent.mkdir(parents=True, exist_ok=True)
        status(f"Preparing official NIST trec_eval {pinned['version']}...")
        status("Fetching trec_eval...")
        try:
            run_captured(["git", "clone", "--no-checkout", pinned["repository"], str(source)], "fetch trec_eval")
            run_captured(["git", "checkout", "--detach", pinned["revision"]], "check out trec_eval", cwd=source)
        except FileNotFoundError as error:
            raise RuntimeError("official trec_eval requires Git to clone the pinned NIST source") from error
    if not binary.is_file():
        status("Building trec_eval...")
        try:
            run_captured(["make"], "build trec_eval", cwd=source)
        except FileNotFoundError as error:
            raise RuntimeError("official trec_eval requires make and a C compiler to build the pinned NIST source") from error
    version = subprocess.check_output([str(binary), "-v"], text=True, stderr=subprocess.STDOUT)
    if f"trec_eval version {pinned['version']}" not in version:
        raise RuntimeError(f"unexpected trec_eval version: {version.strip()}")
    status("trec_eval ready.")
    _TREC_EVAL_BINARY = binary
    return binary


def run_captured(command: list[str], action: str, *, cwd: Path | None = None) -> None:
    """Run a setup command quietly, emitting its diagnostics only on failure."""
    completed = subprocess.run(command, cwd=cwd, text=True, capture_output=True)
    if completed.returncode == 0:
        return
    output = "".join(part for part in (completed.stdout, completed.stderr) if part)
    if output:
        print(output, end="" if output.endswith("\n") else "\n", file=sys.stderr)
    raise RuntimeError(f"failed to {action}; see the captured output above")


def parse_trec_eval(output: str) -> dict[tuple[str, str], float]:
    values: dict[tuple[str, str], float] = {}
    for line in output.splitlines():
        fields = line.split()
        if len(fields) != 3:
            raise ValueError(f"invalid trec_eval output: {line!r}")
        measure, qid, value = fields
        if (measure, qid) in values:
            raise ValueError(f"duplicate trec_eval value: {(measure, qid)}")
        values[(measure, qid)] = float(value)
    return values


def macro_f1(per_query: dict[tuple[str, str], float], qids: list[str]) -> float:
    """Macro F1@10 from official per-query P@10 and Recall@10 only."""
    values = []
    for qid in qids:
        # ``-c`` treats omitted no-result queries as zero precision and recall.
        precision = per_query.get(("P_10", qid), 0.0)
        recall = per_query.get(("recall_10", qid), 0.0)
        values.append(2 * precision * recall / (precision + recall) if precision + recall else 0.0)
    return sum(values) / len(values)


def score_run(qrels: Path, topics: list[tuple[str, str]], run: Path) -> tuple[dict[str, float], dict]:
    """Use official trec_eval; MRR uses -M 10 and F1 is the sole derivative."""
    binary = trec_eval_binary()
    measure_options = [option for measure in TREC_EVAL_MEASURES for option in ("-m", measure)]
    aggregate_command = [str(binary), "-c", *measure_options, str(qrels), str(run)]
    aggregate = parse_trec_eval(subprocess.check_output(aggregate_command, text=True))
    labels = {
        "nDCG@10": "ndcg_cut_10",
        "Recall@10": "recall_10",
        "Recall@100": "recall_100",
        "Precision@10": "P_10",
    }
    scores = {label: aggregate[(measure, "all")] for label, measure in labels.items()}
    mrr_command = [
        str(binary), "-c", "-M", str(MRR_CUTOFF), "-m", "recip_rank", str(qrels), str(run)
    ]
    scores["MRR@10"] = parse_trec_eval(subprocess.check_output(mrr_command, text=True))[("recip_rank", "all")]
    per_query_command = [
        str(binary), "-c", "-q", "-m", "P.10", "-m", "recall.10", str(qrels), str(run)
    ]
    per_query = parse_trec_eval(subprocess.check_output(per_query_command, text=True))
    qids = [qid for qid, _ in topics]
    scored_qids = {qid for measure, qid in per_query if measure == "P_10" and qid != "all"}
    if not scored_qids <= set(qids):
        raise ValueError("trec_eval query population contains an unexpected query")
    scores["F1@10"] = macro_f1(per_query, qids)
    provenance = {
        "binary": str(binary),
        "repository": CONFIG["trec_eval"]["repository"],
        "revision": CONFIG["trec_eval"]["revision"],
        "version": CONFIG["trec_eval"]["version"],
        "aggregate_command": aggregate_command[1:],
        "mrr_command": mrr_command[1:],
        "f1_per_query_command": per_query_command[1:],
    }
    return scores, provenance


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".partial")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def remove_test_index(endpoint: str, index: str) -> None:
    """Remove one disposable test index, leaving all full-run indexes intact."""
    try:
        es_request("DELETE", endpoint, f"/{index}")
    except HTTPError as error:
        if error.code != 404:
            raise


def reset_test_state(endpoint: str, result: Path) -> None:
    """Replace only generated test artifacts so ``--test`` is rerunnable."""
    if result.exists():
        shutil.rmtree(result)
    for arm in ARMS:
        remove_test_index(endpoint, f"miracl-test-{arm}")


def validate_run(topics: list[tuple[str, str]], run: Path, *, require_full_depth: bool = True) -> None:
    """Validate complete, unique TREC output at or below the requested depth.

    Full MIRACL runs must contain 100 results per topic. The 500-document test
    fixture still requests 100, but a sparse lexical query can legitimately
    match fewer documents; its run remains valid for the same official scorer.
    """
    rows: dict[str, list[str]] = {}
    for line in run.read_text(encoding="utf-8").splitlines():
        fields = line.split()
        if len(fields) != 6 or fields[1] != "Q0":
            raise ValueError(f"invalid TREC row in {run}: {line!r}")
        qid, docid, rank = fields[0], fields[2], int(fields[3])
        if rank != len(rows.get(qid, [])) + 1:
            raise ValueError(f"non-contiguous rank in {run}: {qid}")
        rows.setdefault(qid, []).append(docid)
    invalid_depth = any(
        not docids
        or len(docids) > RETRIEVAL_DEPTH
        or len(set(docids)) != len(docids)
        or (require_full_depth and len(docids) != RETRIEVAL_DEPTH)
        for docids in rows.values()
    )
    if set(rows) != {qid for qid, _ in topics} or invalid_depth:
        raise ValueError(f"invalid TREC coverage/depth in {run}")


def write_report(result: Path, title: str, scores: dict[str, dict[str, float]], details: list[str]) -> None:
    lines = [
        f"# {title}",
        "",
        *details,
        "",
        "| Analyzer | " + " | ".join(METRICS) + " |",
        "| --- | " + " | ".join("---:" for _ in METRICS) + " |",
    ]
    lines += [
        "| " + arm_label(arm) + " | "
        + " | ".join(f"{scores[arm][metric]:.6f}" for metric in METRICS)
        + " |"
        for arm in ARMS
    ]
    (result / "benchmark.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def index_full_arm(
    endpoint: str,
    arm: str,
    analyzer: str,
    result: Path,
    documents,
    expected_documents: int,
    index_prefix: str,
) -> dict:
    """Index one treatment with durable checkpoints that safely support resume."""
    status(f"Indexing {arm_label(arm)}...")
    index = f"{index_prefix}-{arm}"
    manifest_path = result / "provenance" / f"{arm}-index.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else None
    try:
        exists = bool(es_request("GET", endpoint, f"/{index}"))
    except HTTPError as error:
        if error.code != 404:
            raise
        exists = False
    if manifest is None:
        if exists:
            raise RuntimeError(f"refusing to adopt unmanifested index: {index}")
        es_request("PUT", endpoint, f"/{index}", index_body(analyzer))
        manifest = {
            "arm": arm,
            "index": index,
            "analyzer": analyzer,
            "state": "indexing",
            "completed_documents": 0,
            "batches": 0,
        }
        write_json(manifest_path, manifest)
    if manifest["analyzer"] != analyzer or manifest["index"] != index:
        raise RuntimeError(f"index checkpoint does not match requested arm: {arm}")
    completed = int(manifest["completed_documents"])
    seen = 0
    digest = hashlib.sha256()
    batch = []
    if completed > expected_documents:
        raise RuntimeError(f"invalid checkpoint count for {arm}: {completed}")
    started = time.monotonic()
    for document in documents:
        digest.update((str(document["docid"]) + "\n").encode())
        seen += 1
        if seen <= completed:
            continue
        batch.append(document)
        if len(batch) == 500:
            bulk_index(endpoint, index, batch, allow_conflicts=completed > 0)
            completed += len(batch)
            batch = []
            manifest.update({
                "completed_documents": completed,
                "batches": int(manifest["batches"]) + 1,
                "state": "indexing",
            })
            write_json(manifest_path, manifest)
            if completed % 100_000 == 0:
                print(f"{arm}: indexed {completed:,}/{expected_documents:,}", flush=True)
    if batch:
        bulk_index(endpoint, index, batch, allow_conflicts=completed > 0)
        completed += len(batch)
        manifest.update({"completed_documents": completed, "batches": int(manifest["batches"]) + 1})
        write_json(manifest_path, manifest)
    if seen != expected_documents or completed != expected_documents:
        raise RuntimeError(
            f"corpus count mismatch for {arm}: seen={seen}, indexed={completed}, expected={expected_documents}"
        )
    es_request("POST", endpoint, f"/{index}/_refresh")
    count = es_request("GET", endpoint, f"/{index}/_count")["count"]
    if count != expected_documents:
        raise RuntimeError(f"index count mismatch for {arm}: {count} != {expected_documents}")
    manifest.update({
        "state": "ready",
        "document_count": count,
        "source_docid_sha256": digest.hexdigest(),
        "indexing_elapsed_seconds": time.monotonic() - started,
    })
    write_json(manifest_path, manifest)
    return manifest


def write_full_outputs(result: Path, scores: dict[str, dict[str, float]], manifests: dict[str, dict]) -> None:
    def improvement(metric: str, baseline: str) -> float:
        return 100 * (scores["bitext-english"][metric] / scores[baseline][metric] - 1)
    expected = CONFIG["miracl"]["expected"]
    details = [
        f"- Elasticsearch: {CONFIG['elasticsearch_version']}",
        f"- Passages: {expected['documents']:,}",
        f"- Dev queries: {expected['queries']}",
        f"- Dev qrels: {expected['qrels']}",
        f"- Plugin SHA-256 (observed): `{sha256(plugin_archive())}`",
        f"- Scorer: official NIST trec_eval {CONFIG['trec_eval']['version']} ({CONFIG['trec_eval']['revision']})",
    ]
    write_report(result, "MIRACL English lexical benchmark", scores, details)
    report = result / "benchmark.md"
    improvement_lines = [
        "## Bitext improvement",
        "",
        "| Baseline | " + " | ".join(METRICS) + " |",
        "| --- | " + " | ".join("---:" for _ in METRICS) + " |",
    ]
    for baseline, label in (
        ("standard", arm_label("standard")),
        ("elastic-english", arm_label("elastic-english")),
    ):
        improvement_lines.append(
            "| " + label + " | "
            + " | ".join(f"{improvement(metric, baseline):.2f}%" for metric in METRICS)
            + " |"
        )
    content = report.read_text(encoding="utf-8") + "\n" + "\n".join(improvement_lines) + "\n"
    report.write_text(content, encoding="utf-8")
    indices = {
        arm: {key: manifest[key] for key in ("analyzer", "document_count", "source_docid_sha256")}
        for arm, manifest in manifests.items()
    }
    provenance = {
        "counts": expected,
        "elasticsearch_version": CONFIG["elasticsearch_version"],
        "indices": indices,
        "plugin_sha256": sha256(plugin_archive()),
        "trec_eval": CONFIG["trec_eval"],
    }
    write_json(result / "provenance.json", provenance)


def run_test() -> None:
    """Exercise all three arms and official metrics without a full-corpus run."""
    status("Benchmark mode: test")
    status(f"Elasticsearch: {CONFIG['elasticsearch_version']}")
    status(f"Bitext English Analyzer plugin: {plugin_version()}")
    status("Preparing MIRACL test data...")
    documents, topics, qrels = miracl.prepare_test_data()
    status(f"Test corpus ready: {len(documents)} passages, {len(topics)} queries.")
    result = RESULTS / "test"
    endpoint = start_elasticsearch(full=False)
    scores: dict[str, dict[str, float]] = {}
    status("Creating benchmark indexes...")
    reset_test_state(endpoint, result)
    for arm, analyzer in ARMS.items():
        status(f"Indexing {arm_label(arm)}...")
        index = f"miracl-test-{arm}"
        es_request("PUT", endpoint, f"/{index}", index_body(analyzer))
        bulk_index(endpoint, index, documents)
        es_request("POST", endpoint, f"/{index}/_refresh")
        if es_request("GET", endpoint, f"/{index}/_count")["count"] != len(documents):
            raise RuntimeError(f"index count mismatch for {arm}")
    scoring_qrels = miracl.qrels_for_topics(topics, result)
    status(f"Running queries at depth {RETRIEVAL_DEPTH}...")
    for arm, analyzer in ARMS.items():
        status(f"Querying {arm_label(arm)}...")
        index = f"miracl-test-{arm}"
        run = result / "runs" / f"{arm}.trec"
        write_trec_run(endpoint, index, analyzer, topics, run)
        validate_run(topics, run, require_full_depth=False)
        status(f"Scoring {arm_label(arm)} with NIST trec_eval {CONFIG['trec_eval']['version']}...")
        scores[arm], scorer = score_run(scoring_qrels, topics, run)
    status("Writing report...")
    write_json(result / "scores.json", scores)
    write_json(result / "provenance" / "trec_eval.json", scorer)
    details = [
        "This deterministic test is not a full-corpus benchmark.",
        "",
        f"- Elasticsearch: {CONFIG['elasticsearch_version']}",
        f"- Plugin SHA-256 (observed): `{sha256(plugin_archive())}`",
        f"- Corpus records: {len(documents)}",
        f"- Queries: {len(topics)}",
        f"- Full development qrels loaded: {sum(map(len, qrels.values()))}",
    ]
    write_report(result, "MIRACL English pipeline test", scores, details)
    status("Results written to results/test/benchmark.md")
    status("Done.")


def run_full() -> None:
    """Run or resume the full corpus without replacing existing canonical runs."""
    status("Benchmark mode: full")
    status(f"Elasticsearch: {CONFIG['elasticsearch_version']}")
    status(f"Bitext English Analyzer plugin: {plugin_version()}")
    status("Preparing MIRACL development data...")
    topics, _ = miracl.load_topics_and_qrels()
    result = RESULTS / "english"
    result.mkdir(parents=True, exist_ok=True)
    endpoint = start_elasticsearch(full=True)
    expected_documents = int(CONFIG["miracl"]["expected"]["documents"])
    status("Creating or resuming benchmark indexes...")
    manifests = {
        arm: index_full_arm(
            endpoint,
            arm,
            analyzer,
            result,
            miracl.corpus_documents(),
            expected_documents,
            "miracl-english",
        )
        for arm, analyzer in ARMS.items()
    }
    if len({manifest["source_docid_sha256"] for manifest in manifests.values()}) != 1:
        raise RuntimeError("the three arms did not consume the same corpus document IDs")
    scores: dict[str, dict[str, float]] = {}
    status(f"Running queries at depth {RETRIEVAL_DEPTH}...")
    for arm, analyzer in ARMS.items():
        status(f"Querying {arm_label(arm)}...")
        run = result / "runs" / f"{arm}.trec"
        if run.exists():
            raise FileExistsError(f"refusing to overwrite canonical run: {run}")
        write_trec_run(endpoint, manifests[arm]["index"], analyzer, topics, run)
        validate_run(topics, run)
        status(f"Scoring {arm_label(arm)} with NIST trec_eval {CONFIG['trec_eval']['version']}...")
        scores[arm], scorer = score_run(miracl.DATA_DIRECTORY / "raw" / "qrels_dev.tsv", topics, run)
    status("Writing report...")
    write_json(result / "scores.json", scores)
    write_json(result / "provenance" / "trec_eval.json", scorer)
    write_full_outputs(result, scores, manifests)
    status("Results written to results/english/benchmark.md")
    status("Done.")


def rescore_full() -> None:
    """Re-score local canonical runs without querying or indexing Elasticsearch."""
    status("Benchmark mode: rescore")
    status("Loading retained canonical runs...")
    topics, _ = miracl.load_topics_and_qrels()
    result, manifests, scores = RESULTS / "english", {}, {}
    for arm in ARMS:
        manifest_path, run = result / "provenance" / f"{arm}-index.json", result / "runs" / f"{arm}.trec"
        if not manifest_path.is_file() or not run.is_file():
            raise FileNotFoundError(f"missing completed canonical artifacts for {arm}")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("state") != "ready" or manifest.get("document_count") != CONFIG["miracl"]["expected"]["documents"]:
            raise ValueError(f"incomplete index manifest for {arm}")
        validate_run(topics, run)
        manifests[arm] = manifest
        status(f"Scoring {arm_label(arm)} with NIST trec_eval {CONFIG['trec_eval']['version']}...")
        scores[arm], scorer = score_run(miracl.DATA_DIRECTORY / "raw" / "qrels_dev.tsv", topics, run)
    if len({manifest["source_docid_sha256"] for manifest in manifests.values()}) != 1:
        raise ValueError("canonical runs do not share a corpus document-ID digest")
    status("Writing report...")
    write_json(result / "scores.json", scores)
    write_json(result / "provenance" / "trec_eval.json", scorer)
    write_full_outputs(result, scores, manifests)
    status("Results written to results/english/benchmark.md")
    status("Done.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("test", "full", "rescore"))
    {"test": run_test, "full": run_full, "rescore": rescore_full}[parser.parse_args().mode]()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
