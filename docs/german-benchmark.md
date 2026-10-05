# Bitext Linguistic Analyzer Improves Elasticsearch German Search Quality by +36% for F1@10

Adapted from the original Bitext blog post: https://www.bitext.com/blog/bitext-linguistic-analyzer-beats-every-elasticsearch-configuration-on-german-search-quality/

This document describes the published German MIRACL benchmark. The current repository provides a fully reproducible English workflow; a reproducible German package is planned separately.

## Executive Summary

In a search benchmark for German, Bitext Linguistic Analysis SDK returned more relevant results and missed fewer useful passages than every tested Elasticsearch configuration. In short, **Bitext Linguistic Analysis improves German search quality by up to 36%**.

The benchmark uses the test data from the MIRACL dataset with 700+ queries and 7,000+ manually annotated relevance judgments and focuses on the top 10 results, the most relevant for RAG:

- Compared with Elasticsearch’s default analyzer, Bitext SDK improved **precision by 35.0%**, **recall by 39.6%**, and the combined **F1 score by 36.1%**
- Compared with Elasticsearch’s built-in German analyzer, Bitext increased **precision by 8.7%**, **recall by 13.6%**, and **F1 by 9.6%**
- Compared to the recommended Elastic German decompounding setup, Bitext increased **precision by 4.3%**, **recall by 10.2%**, and **F1 by 5.5%**

For users, the impact is straightforward: more relevant results, less retrieval noise, stronger candidate sets for reranking and RAG, and better evidence for search applications and AI agents before any expensive downstream model is applied.

Because these gains were confirmed on an industry-standard test set, they provide evidence that better linguistic analysis can strengthen the retrieval layer used by enterprise search, hybrid retrieval, RAG, and agentic workflows.

## The Benchmark Data

Text analysis is one of the most important, and frequently underestimated, parts of search and AI pipelines. Before lexical search, vector search, reranking, RAG, or an AI agent can use a document, the system must decide which words and linguistic relationships to represent.

A basic analyzer with tokenization and lowercasing but no language-specific morphological analysis can miss valid morphological relationships that convey meaning. Classical stemming can discover some of these relationships and improve recall, but it can also hurt precision because the analysis is based on word endings rather than actual word morphology. Splitting compounds exposes some useful subwords, but it can also introduce duplicates and noisy terms.

Bitext Linguistic Analysis SDK addresses this problem through a combination of:

- original-form preservation and stopword handling, provided by Elastic
- German-specific normalization, provided by Elastic
- full-token lemmatization, provided by Bitext SDK
- compound analysis and lemmatization, provided by Bitext SDK

We evaluated this pipeline in a controlled Elasticsearch benchmark using German MIRACL datasets. MIRACL (Multilingual Information Retrieval Across a Continuum of Languages) is an open research initiative widely adopted by academic groups around the world. It was created to provide high-quality datasets and benchmarks for evaluating retrieval systems across many languages, including languages with relatively limited digital resources.

## The Benchmark Setup

The final evaluation used:

- **Target document database:** 15,866,222 German Wikipedia passages
- **Queries:** 712 German MIRACL test topics
- **Evaluation judgments:** 7,317 MIRACL test relevance judgments
- The same Elasticsearch version, corpus, settings, and evaluation code for every configuration
- Evaluation focused on the top 10 results because those ranks are especially important for interactive search, reranking, RAG candidate selection, and agentic retrieval
- Frozen indices and query configurations, with no tuning after the test results were observed

## The Four Competing Approaches to German Text Analysis

The comparison included four different approaches to text analysis: three approaches provided by Elastic and a fourth based on Bitext Linguistic Analysis. The objective was to determine whether Bitext could improve on all three alternatives commonly available in major search engines.

### Approach 1 – Elasticsearch Default Standard Analysis

Standard tokenization and lowercasing, without linguistic analysis, stemming, or lemmatization.

### Approach 2 – Elasticsearch Built-in German Analyzer

Adds normalization of German phenomena, stopword removal, and light stemming to Approach 1.

### Approach 3 – Elastic German Decompounder

Adds analysis of full compound stems and splitting of component stems to Approach 2.

### Approach 4 – Bitext Linguistic Analysis

Builds its own linguistic data from scratch, providing lemmatization instead of Elastic stemming and linguistic decompounding instead of Elastic compound stemming.

## The Results

| Configuration | nDCG@10 | Recall@10 | Precision@10 | F1@10 | MRR@10 |
|---|---:|---:|---:|---:|---:|
| Approach 1 | 0.157726 | 0.197563 | 0.055758 | 0.080585 | 0.204049 |
| Approach 2 | 0.188757 | 0.242742 | 0.069242 | 0.100065 | 0.237202 |
| Approach 3 | 0.197915 | 0.250250 | 0.072191 | 0.103969 | 0.252236 |
| **Approach 4 – Bitext** | **0.206119** | **0.275821** | **0.075281** | **0.109650** | **0.256227** |

Meaning of the metrics:

- **nDCG@10** measures ranking quality in the first ten results, rewarding systems that place known relevant passages higher
- **Precision@10** measures the proportion of the first ten results that are relevant
- **Recall@10** measures how much of the known relevant material appears on the first result page
- **F1@10** balances first-page precision and recall
- **MRR@10** measures how early the first relevant result appears

The full evaluation covered all 712 queries. Approach 4, based on Bitext Linguistic Analysis, produced improvements across every measured dimension. The Bitext configuration achieved the highest nDCG, recall, precision, F1, and MRR among all reported configurations.

| Comparison | nDCG@10 | Recall@10 | Precision@10 | F1@10 | MRR@10 |
|---|---:|---:|---:|---:|---:|
| Approach 4 vs. Approach 1 | +30.7% | +39.6% | +35.0% | +36.1% | +25.6% |
| Approach 4 vs. Approach 2 | +9.2% | +13.6% | +8.7% | +9.6% | +8.0% |
| Approach 4 vs. Approach 3 | +4.1% | +10.2% | +4.3% | +5.5% | +1.6% |

**Key result:** Bitext outperformed the Elasticsearch default analyzer, the built-in German analyzer, and the recommended Elastic German decompounding configuration.

The largest improvement was a **36.1% increase in F1** compared with the default Elasticsearch configuration.

## Examples of Actual Search Cases

The companion examples file presents examples of different German linguistic phenomena and how they are handled by the four approaches:

- [`german-examples.md`](german-examples.md)

These examples help explain the improvements delivered by Bitext Linguistic Analysis.

## Why the Results Matter

The benchmark shows that linguistic analysis of input text, before downstream tasks such as search, improves retrieval results – primarily through lemmatization and compound analysis.

Elastic’s built-in German analysis, Approach 2, produced a major improvement over standard analysis, Approach 1. Adding index-time decompounding, Approach 3, improved the Elastic result further. This confirms that German compound structure provides useful retrieval evidence.

Bitext Linguistic Analysis, Approach 4, improved again over all three approaches by replacing approximate full-token stemming with dictionary-based lemmatization and by linguistically splitting and representing compound components as lemmas.

This provides a linguistically controlled document representation combining:

```text
Original token
+ Full-token lemma
+ Component lemmas
```

The system therefore gains component-level matching in the document index without indiscriminately expanding every query.

### When Text Preprocessing Misses Valid Word Forms or Compound Relationships

- Relevant documents never enter the candidate set
- Rerankers have nothing to rescue
- RAG systems ground answers in weaker evidence
- AI agents may fail to find the source required to complete a task

### When Stemming Introduces Noisy Terms

- Search-term statistics are distorted
- Irrelevant documents may be promoted
- More expensive downstream models must compensate

In short, linguistic analysis strengthens the retrieval layer before those expensive downstream costs are incurred.

## What This Means for Search and AI Systems

Better linguistic analysis improves the retrieval evidence available to every downstream stage:

- **For lexical search:** it improves lexical matching and top-page ranking
- **For hybrid retrieval:** it strengthens the sparse lexical channel before it is combined with embeddings
- **For RAG:** it improves the candidate passages supplied to rerankers and language models
- **For AI agents:** it reduces the risk that a useful document is missed because the query and the document use different inflected or compound forms

Most importantly, the benchmark does not claim that linguistic analysis replaces vector retrieval, reranking, or LLM reasoning. It shows that stronger linguistic normalization can provide these pipelines with better lexical retrieval evidence at the start.

## Conclusion

The German MIRACL evaluation supports three conclusions:

- German-specific stemming (Approach 2) improves over Elasticsearch’s default standard analyzer (Approach 1)
- Compound-aware indexing (Approach 3) improves over stemming (Approach 2)
- Bitext Linguistic Analysis (Approach 4) produces the strongest top-ranking results by combining full-token lemmatization with linguistic compound splitting and component lemmatization

The practical takeaway is not that linguistic analysis replaces modern ranking or generation systems. It is that those systems perform better when the lexical evidence entering the pipeline is more accurate.

Search quality can be improved before adding another model, reranker, or generation layer. Full-token lemmatization and controlled compound analysis provide stronger lexical evidence at the beginning of the retrieval pipeline.
