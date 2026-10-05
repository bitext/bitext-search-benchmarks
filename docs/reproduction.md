# Reproducing the English MIRACL benchmark

This document explains how to reproduce the English lexical-search benchmark end to end, what the scripts do, where generated files are written, and how the benchmark is scored.

The benchmark compares three analyzer configurations on the same MIRACL English corpus:

1. **Elasticsearch Standard**
2. **Elasticsearch English**
3. **Bitext English Analyzer**

All three configurations use Elasticsearch 9.5.4, Lucene BM25 with `k1 = 1.2` and `b = 0.75`, one primary shard, no replicas, the same indexed fields, the same queries, and the same scoring procedure. The analyzer is the treatment variable.

## Requirements

The benchmark requires:

- Python 3.10 or later
- Git
- Docker with Docker Compose v2 (`docker compose`)
- `make` and a C compiler, used only to build the pinned official NIST `trec_eval`
- Internet access for the first run, to download MIRACL data, the Elasticsearch image, and the pinned `trec_eval` source

You do **not** need to install Elasticsearch or `trec_eval` separately.

### Ubuntu / Debian

Install Git, Python, and the standard C build tools:

```bash
sudo apt update
sudo apt install -y \
  git \
  python3 \
  build-essential \
  ca-certificates
```

Check the Python version:

```bash
python3 --version
```

Python must be **3.10 or later**. If the `python3` package supplied by your distribution is older, install a newer supported Python version before continuing.

Install Docker Engine and the Docker Compose plugin using Docker's official instructions for your distribution:

- Ubuntu: <https://docs.docker.com/engine/install/ubuntu/>
- Debian: <https://docs.docker.com/engine/install/debian/>
- Linux post-installation: <https://docs.docker.com/engine/install/linux-postinstall/>

The benchmark invokes `docker` directly, so your user must be able to use Docker without prefixing every command with `sudo`.

Verify the prerequisites:

```bash
python3 --version
git --version
make --version
cc --version
docker --version
docker compose version
```

### macOS

Install Apple's Command Line Tools:

```bash
xcode-select --install
```

They provide Git, `make`, and the Clang C compiler required to build `trec_eval`.

Install Python 3.10 or later. If you use Homebrew:

```bash
brew install python
```

Install Docker Desktop for Mac and start it before running the benchmark:

<https://docs.docker.com/desktop/setup/install/mac-install/>

Verify the prerequisites:

```bash
python3 --version
git --version
make --version
cc --version
docker --version
docker compose version
```

On macOS, keep the repository and any custom Elasticsearch data directory in a location shared with Docker Desktop, such as your home directory or an explicitly shared volume.

Before starting the full benchmark on any new machine or platform, run `--test` first.

## Clone the repository

```bash
git clone https://github.com/bitext/bitext-search-benchmarks.git
cd bitext-search-benchmarks
```

The repository contains the Bitext English Analyzer Elasticsearch plugin under `plugin/`. The analyzer source is published separately at:

<https://github.com/bitext/bitext-lucene-english-analyzer>

## Start with the test mode

Run:

```bash
./run_benchmark.sh --test
```

Test mode uses real MIRACL English data but keeps the run small enough for repeated validation.

It deterministically selects:

- 50 real MIRACL development queries
- every positively judged passage for those queries that is required by the fixture
- deterministic real MIRACL distractor passages
- exactly 500 unique passages in total, drawn from the first two corpus shards

The current fixture contains all positive judgments for the selected topics, so the scoring path exercises real non-zero relevance judgments rather than only testing file plumbing.

Each test run:

1. downloads the pinned MIRACL topics, qrels, and first two corpus shards if they are not already cached
2. starts Elasticsearch 9.5.4 with the bundled Bitext plugin
3. creates three disposable test indexes
4. indexes the same 500 passages into all three indexes
5. runs the same 50 queries against each analyzer
6. retrieves up to 100 documents per query
7. writes standard six-column TREC run files
8. obtains and builds the pinned official NIST `trec_eval` if necessary
9. scores all three runs
10. writes scores, provenance, and a Markdown report under `results/test/`

`--test` is designed to be rerunnable. Before rebuilding, it removes only its own `miracl-test-*` indexes and `results/test/`. It does not remove or alter full benchmark indexes or `results/english/`.

## Run the full benchmark

Run:

```bash
./run_benchmark.sh --full
```

The full benchmark uses:

- 32,893,221 English Wikipedia passages
- 799 MIRACL development queries
- 8,350 original MIRACL relevance judgments
- retrieval depth 100

The full run is resource-intensive. In our qualification environment:

- Elasticsearch used a **24 GiB heap**
- the complete benchmark consumed roughly **544 GB of local storage** across downloaded data, indexes, and generated artifacts

Allow substantial additional headroom when choosing a machine or disk.

### What `--full` does

The full pipeline proceeds as follows.

#### 1. Load the pinned benchmark configuration

`scripts/config/benchmark.json` pins:

- Elasticsearch 9.5.4
- the MIRACL corpus and benchmark dataset revisions
- the official NIST `trec_eval` revision
- expected document, query, and qrel counts
- BM25 parameters

The script validates the MIRACL query and qrel counts before proceeding.

#### 2. Acquire MIRACL

The script downloads MIRACL directly from revision-pinned Hugging Face dataset URLs.

Generated input data is stored under:

```text
data/miracl/en/
```

The full corpus consists of 66 compressed JSONL shards. Files that already exist are reused rather than downloaded again.

The expected full-corpus document count is validated against 32,893,221 passages.

#### 3. Start Elasticsearch

The benchmark builds the Docker image described by `scripts/docker/Dockerfile`.

That image is based on Elasticsearch 9.5.4 and installs the single plugin ZIP present under `plugin/`.

Elasticsearch data is stored by default under:

```text
data/elasticsearch/
```

This is a host bind mount, so the potentially large Elasticsearch data directory remains visible and under your control rather than being hidden in a Docker-managed named volume.

The script verifies that Elasticsearch can write the selected directory before starting the service.

#### 4. Create and index the three benchmark arms

The full benchmark uses three indexes:

- Elasticsearch Standard
- Elasticsearch English
- Bitext English Analyzer

Every arm indexes the same document IDs and the same `title`, `text`, and combined `contents` fields.

All three use:

- one primary shard
- no replicas
- BM25 `k1 = 1.2`
- BM25 `b = 0.75`

Only the analyzer changes.

Full indexing is checkpointed on disk. If indexing is interrupted, rerunning `./run_benchmark.sh --full` can resume from the recorded progress instead of starting the completed portion from scratch.

The pipeline validates that each completed index contains exactly 32,893,221 documents and that all three arms consumed the same corpus document IDs.

#### 5. Run the MIRACL development queries

For each of the 799 development queries, each arm retrieves the top 100 documents.

Ranking is ordered by:

1. Elasticsearch score, descending
2. document ID, ascending, to make score ties deterministic

Each run is written in standard six-column TREC format.

#### 6. Build and run official NIST `trec_eval`

The benchmark does not use a system-installed scorer.

On first use, it clones the official NIST repository:

<https://github.com/usnistgov/trec_eval>

and checks out the exact pinned revision:

```text
d4dd9d9ca4b7984fc48788052503cc4d1644c529
```

corresponding to `trec_eval` 9.0.8.

The pinned source is built with its normal upstream `make` build under:

```text
data/tools/trec_eval/d4dd9d9ca4b7984fc48788052503cc4d1644c529/source/
```

Later runs reuse that exact checkout and binary after verifying the revision and version.

The benchmark never silently falls back to a `trec_eval` executable found on `PATH`.

#### 7. Score the runs

The benchmark reports:

- nDCG@10
- Recall@10
- Recall@100
- Precision@10
- F1@10
- MRR@10

The official scorer evaluates the complete MIRACL qrel population with `-c`, so queries without retrieved results remain part of the evaluation population.

The following metrics come directly from official `trec_eval`:

- nDCG@10: `ndcg_cut_10`
- Precision@10: `P_10`
- Recall@10: `recall_10`
- Recall@100: `recall_100`
- MRR@10: `recip_rank`, evaluated separately with retrieval capped at rank 10

`trec_eval` does not provide the benchmark's required ranked F1-at-cutoff aggregation directly. F1@10 is therefore the only derived metric:

1. obtain per-query `P_10` from official `trec_eval`
2. obtain per-query `recall_10` from official `trec_eval`
3. calculate F1 for each query
4. macro-average the per-query F1 values

F1@10 is **not** calculated from the aggregate Precision@10 and Recall@10 values.

#### 8. Write reports and provenance

The completed full run is written under:

```text
results/english/
```

including:

```text
results/english/
├── benchmark.md
├── scores.json
├── provenance.json
├── runs/
│   ├── standard.trec
│   ├── elastic-english.trec
│   └── bitext-english.trec
└── provenance/
    ├── standard-index.json
    ├── elastic-english-index.json
    ├── bitext-english-index.json
    └── trec_eval.json
```

The generated provenance records include the Elasticsearch version, observed plugin artifact identity, corpus/index validation information, and the exact scorer revision and commands used.

`data/` and `results/` are generated runtime directories and are excluded from Git.

## Re-score existing full runs

If full TREC runs already exist and you only want to regenerate scores and reports, use:

```bash
./run_benchmark.sh --rescore
```

This mode reuses the completed canonical TREC runs and qrels. It does not rerun retrieval or reindex the corpus.

It validates the retained run depth and index manifests before producing replacement score/report output.

## Runtime directories

By default, the benchmark creates:

```text
data/
├── elasticsearch/
├── miracl/
│   └── en/
└── tools/
    └── trec_eval/

results/
├── test/
└── english/
```

These directories can become large and are intentionally excluded from version control.

## Configuration and environment variables

### `MIRACL_ES_DATA_DIR`

Overrides the host directory used for Elasticsearch data.

Default:

```text
<repository>/data/elasticsearch/
```

Example:

```bash
MIRACL_ES_DATA_DIR=/mnt/large-disk/miracl-elasticsearch \
  ./run_benchmark.sh --full
```

Use this when the repository filesystem does not have enough space for the full indexes.

### `MIRACL_ES_JAVA_OPTS`

Overrides the Elasticsearch JVM options.

Defaults:

- `--test`: `-Xms2g -Xmx2g`
- `--full`: `-Xms24g -Xmx24g`

Example:

```bash
MIRACL_ES_JAVA_OPTS="-Xms24g -Xmx24g" \
  ./run_benchmark.sh --full
```

The qualified full benchmark used the 24 GiB default. If you lower the heap substantially, the full run may fail or perform poorly.

### `MIRACL_ES_PORT`

Overrides the host Elasticsearch port.

Default:

```text
9200
```

Example:

```bash
MIRACL_ES_PORT=19200 ./run_benchmark.sh --test
```

## Restart and overwrite behavior

### Test mode

`--test` is disposable and rerunnable. It replaces only:

- the three `miracl-test-*` indexes
- `results/test/`

### Full indexing

`--full` maintains per-arm indexing checkpoints under `results/english/provenance/`.

If indexing is interrupted, rerun:

```bash
./run_benchmark.sh --full
```

and the pipeline resumes from its recorded progress.

Do not delete the index manifests if you intend to resume an interrupted full index.

### Canonical full TREC runs

The full pipeline deliberately refuses to overwrite an existing canonical run file. This prevents an expensive completed run from being silently replaced.

If you intentionally want a completely new full benchmark, preserve or remove the previous generated state deliberately rather than relying on the script to overwrite it.

## Stopping Elasticsearch

The benchmark starts Elasticsearch in the background with Docker Compose.

To stop the container without deleting the generated Elasticsearch data:

```bash
docker compose -f scripts/docker/compose.yml down
```

The bind-mounted data remains in `data/elasticsearch/` or in the directory selected with `MIRACL_ES_DATA_DIR`.

Do not delete that directory unless you intentionally want to discard the indexes.

## Expected published English results

A successful full run with the published configuration should reproduce the following scores:

| Analyzer | nDCG@10 | Recall@10 | Recall@100 | Precision@10 | F1@10 | MRR@10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Elasticsearch Standard | 0.250600 | 0.321200 | 0.644800 | 0.089400 | 0.129218 | 0.304500 |
| Elasticsearch English | 0.267200 | 0.347600 | 0.727700 | 0.099100 | 0.142206 | 0.322300 |
| Bitext English Analyzer | 0.290000 | 0.373900 | 0.740300 | 0.107000 | 0.153541 | 0.346800 |

Small differences should be investigated rather than silently normalized away.

## Troubleshooting

### Docker cannot write the Elasticsearch data directory

Set `MIRACL_ES_DATA_DIR` to a host directory that Docker can write.

On Linux, verify ownership and permissions without using broad permissions such as `chmod 777`.

On macOS, verify that the directory is available to Docker Desktop's file-sharing layer.

### Port 9200 is already in use

Choose another host port:

```bash
MIRACL_ES_PORT=19200 ./run_benchmark.sh --test
```

### `trec_eval` cannot be built

Verify:

```bash
git --version
make --version
cc --version
```

The benchmark intentionally builds the exact pinned official scorer and does not substitute a system-installed implementation.

### A full run was interrupted

Rerun:

```bash
./run_benchmark.sh --full
```

The indexing checkpoints are designed to resume completed progress.

If the failure occurred for reasons other than an interrupted indexing process, inspect the error before removing any generated state.
