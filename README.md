# Linguistic Analysis Improves Lexical Search Accuracy: +18% F1@10 in English, +36% F1@10 in German

## A Multilingual Benchmark Based on Elasticsearch and MIRACL

### Does linguistic analysis improve lexical retrieval?

We ran a benchmark to test a simple hypothesis: can deeper linguistic analysis, including tokenization, lemmatization, and language-specific phenomena such as compounding, significantly improve lexical search accuracy?

We benchmarked English and German against two common approaches used in search systems: plain tokenization and tokenization plus stemming. Both languages benefit from deeper linguistic analysis. F1@10 improves by more than 18% for English and by more than 36% for German. This repository makes the English benchmark reproducible so that the results can be tested, inspected, extended, and improved.

Beyond the percentages, the examples show why linguistic analysis matters. Lexical search remains an important complement to vector retrieval in hybrid search, and seemingly small normalization decisions can connect terms that should remain distinct or fail to connect forms that belong together.

In Elasticsearch's English stemming pipeline, for example:

- `organism` and `organization` can both be reduced to `organ`
- `United` and `unit` can both be reduced to `unit`
- `US`, `use`, and `used` can all be reduced to `us`

Lemmatization avoids many of these false conflations while also handling relationships that suffix stemming misses.

### Why start with English?

English is often treated as a language that requires little language-specific analysis, or one that can be handled adequately with a standard stemmer. Its comparatively limited inflectional morphology has reinforced that view.

That makes English a useful test case. If linguistic analysis can improve search accuracy even for English, similar or greater gains may be possible for languages where morphology and word formation play a larger role. German and Korean, for example, make extensive use of compounding, while Spanish and French have substantially richer inflectional morphology.

The repository currently makes the English benchmark fully reproducible. We plan to publish the corresponding reproducible German benchmark separately.

## What we benchmark

We compare three approaches to English text analysis:

1. **Elasticsearch Standard**: standard tokenization and lowercasing, with no English-specific stemming or lemmatization

   `Documents → Elasticsearch Standard → Lucene → BM25`

2. **Elasticsearch English**: standard tokenization, possessive normalization, lowercasing, English stopword removal, and Porter stemming

   `Documents → Elasticsearch English → Lucene → BM25`

3. **Bitext English Analyzer**: sentence-aware tokenization, possessive normalization, contextual handling of named entities, lemmatization, lowercasing, and English stopword removal

   `Documents → Bitext English Analyzer → Lucene → BM25`

The Bitext English Analyzer is implemented in Java as an Elasticsearch stable plugin. Its source code is published in the [`bitext-lucene-english-analyzer`](https://github.com/bitext/bitext-lucene-english-analyzer) repository.

Except for the analyzer being tested, all three configurations use the same indexing, retrieval, and evaluation setup.

## Benchmark metrics

We report:

- **nDCG@10**, which measures ranking quality in the first ten results and rewards systems that place known-relevant passages higher
- **Recall@10**, which measures how much of the known-relevant material appears in the first ten results
- **Recall@100**, which measures how much of the known-relevant material appears in the first hundred results
- **Precision@10**, which measures the proportion of the first ten results that is known relevant
- **F1@10**, which balances per-query Precision@10 and Recall@10
- **MRR@10**, which measures how early the first known-relevant passage appears, with evaluation capped at rank 10

The benchmark uses the official NIST `trec_eval` scorer for the standard retrieval metrics. F1@10 is derived per query from `trec_eval`'s Precision@10 and Recall@10 values and then macro-averaged.

## Benchmark setup

The English benchmark uses:

- **Dataset:** MIRACL English
  - 32,893,221 English Wikipedia passages
  - 799 development queries
  - 8,350 original MIRACL relevance judgments
- **Search engine:** Elasticsearch 9.5.4
- **Ranking:** Lucene BM25
- **BM25 parameters:** `k1 = 1.2`, `b = 0.75`
- **Index layout:** one primary shard, no replicas
- **Fields:** identical title and passage fields in all three arms
- **Retrieval depth:** 100 documents per query
- **Evaluation:** the same queries, qrels, retrieval settings, and official TREC scoring for all three arms

## Benchmark results

The following results were produced with Elasticsearch 9.5.4 and are reproducible with the workflow in this repository.

| Analyzer | nDCG@10 | Recall@10 | Recall@100 | Precision@10 | F1@10 | MRR@10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Elasticsearch Standard | 0.250600 | 0.321200 | 0.644800 | 0.089400 | 0.129218 | 0.304500 |
| Elasticsearch English | 0.267200 | 0.347600 | 0.727700 | 0.099100 | 0.142206 | 0.322300 |
| Bitext English Analyzer | 0.290000 | 0.373900 | 0.740300 | 0.107000 | 0.153541 | 0.346800 |

Across the five top-10 metrics, the Bitext English Analyzer improves over **Elasticsearch Standard** by **more than 16% on average**:

- nDCG@10: **+15.72%**
- Recall@10: **+16.41%**
- Precision@10: **+19.69%**
- F1@10: **+18.82%**
- MRR@10: **+13.89%**

At depth 100, Recall@100 improves by **14.81%**.

Across the same five top-10 metrics, the Bitext English Analyzer improves over **Elasticsearch English** by **more than 7% on average**:

- nDCG@10: **+8.53%**
- Recall@10: **+7.57%**
- Precision@10: **+7.97%**
- F1@10: **+7.97%**
- MRR@10: **+7.60%**

At depth 100, Recall@100 improves by **1.73%**.

## Examples of recurring issues that linguistic analysis solves

### Avoiding over-stemming

A stemmer may improve recall by conflating related forms, but the conflation is not always linguistically sound. For example, the Porter stemmer reduces `majority` to `major`. The Bitext analyzer preserves the lexical identity of `majority` rather than merging it with the adjective and noun `major`.

Over-stemming is particularly damaging because it introduces false matches rather than merely missing a relationship.

### Preserving names and unique strings

Named entities are often built from ordinary words. `General` and `Motors` are morphologically analyzable in isolation, but in `General Motors` they are parts of a company name. The sentence-aware Bitext analyzer preserves the entity terms in context instead of reducing them to stems such as `gener` and `motor`.

The same issue occurs with organizations, products, policies, locations, technical names, and other multiword entities.

### Handling irregular morphology

Dictionary-based lemmatization can connect forms that suffix stemming misses, for example:

- `meaning` / `meant` → `mean`
- `sell` / `sold` → `sell`
- `make` / `made` → `make`
- `come` / `came` → `come`

These are ordinary English relationships. When a query and a relevant passage use different irregular forms, suffix stemming may leave them disconnected.

See [English benchmark examples](docs/english-examples.md) for detailed MIRACL examples.

## Reproduce the English benchmark

The repository contains the scripts, configuration, and Bitext Elasticsearch plugin needed to reproduce the English benchmark. Generated datasets, Elasticsearch indexes, TREC runs, scores, and reports are created locally and are not stored in Git.

### Requirements

You need:

- Python 3.10 or later
- Git
- Docker with Docker Compose v2
- `make` and a C compiler, used to build the pinned official NIST `trec_eval`

After cloning the repository, run the lightweight end-to-end test first:

```bash
./run_benchmark.sh --test
```

This uses real MIRACL data but only a deterministic 500-passage, 50-query fixture drawn from the first two corpus shards. It exercises data acquisition, all three analyzers, Elasticsearch indexing and retrieval, depth-100 TREC output, official scoring, and report generation.

To run the complete 32,893,221-passage benchmark:

```bash
./run_benchmark.sh --full
```

The full run downloads the revision-pinned MIRACL corpus, starts Elasticsearch 9.5.4 with the bundled Bitext English Analyzer plugin, indexes the same corpus under all three analysis configurations, retrieves the top 100 documents for all 799 development queries, scores the runs with the pinned official NIST `trec_eval`, and generates the final report.

Downloaded and runtime data are written under `data/` by default. Generated benchmark output is written under `results/`. Both directories are excluded from Git.

The complete run is resource-intensive. Our qualification run used a 24 GiB Elasticsearch heap and roughly 544 GB of local storage across downloaded data, Elasticsearch indexes, and generated artifacts. Elasticsearch storage can be moved to another disk with `MIRACL_ES_DATA_DIR`.

See [Reproducing the benchmark](docs/reproduction.md) for installation instructions, the complete step-by-step workflow, scoring details, output paths, restart behavior, configuration options, and cleanup guidance.

## German benchmark

In German, the accuracy gains from linguistic analysis, including lemmatization and decompounding, are larger. German combines richer inflection with highly productive compounding, making it a useful example of how the benefits of linguistic processing can increase with morphological and word-formation complexity.

The German benchmark has not yet been packaged here as a fully reproducible workflow. See [German benchmark results](docs/german-benchmark.md) for the published German evaluation.

## License

This repository is released under the [Apache License 2.0](LICENSE).
