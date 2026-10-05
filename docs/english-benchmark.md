# Bitext Linguistic Analyzer Improves Elasticsearch English Search Quality by +18% for F1@10

Adapted from the original Bitext blog post: https://www.bitext.com/blog/bitext-linguistic-analyzer-improves-elasticsearchs-english-search-quality/

## Executive Summary

Our earlier [German MIRACL benchmark](german-benchmark.md) showed that linguistic analysis can substantially improve lexical search in a morphologically complex language. The obvious follow-up question was harder: does richer linguistic analysis still matter in English, where stemming is mature, inexpensive, and often assumed to be good enough?

We tested three Elasticsearch 9.5.4 analyzer configurations on the public English MIRACL development benchmark:

1. **Elasticsearch Standard:** standard tokenization and lowercasing, with no English-specific stemming or lemmatization
2. **Elasticsearch English:** standard tokenization, possessive normalization, lowercasing, English stopword removal, and Porter stemming
3. **Bitext English:** sentence-aware tokenization, possessive normalization, contextual handling of named entities, lemmatization, lowercasing, and English stopword removal

Bitext English builds upon the components of Elasticsearch’s built-in English analyzer by:

- adding more intelligent case handling, including preserving case through lexical analysis, using sentence-aware tokenization to distinguish sentence-initial capitalization from meaningful capitalization, and deferring lowercasing until after lexical and entity decisions have been made
- replacing Porter stemming with dictionary-based lemmatization, while preserving original word forms alongside their lemmas to retain exact-match evidence
- adding contextual handling of named-entity terms, so words that are part of names can be protected from inappropriate ordinary-word normalization while the same forms can still be lemmatized when used as regular vocabulary

The answer was clear. Across the five top-10 metrics, Bitext English improved over Elasticsearch Standard by an average of more than **16%**:

- **nDCG@10 by 15.72%**
- **Recall@10 by 16.41%**
- **Precision@10 by 19.69%**
- **F1@10 by 18.82%**
- **MRR@10 by 13.89%**

At depth 100, **Recall@100 improved by 14.81%**.

Compared with Elasticsearch English, Bitext improved the same five top-10 metrics by an average of more than **7%**:

- **nDCG@10 by 8.53%**
- **Recall@10 by 7.57%**
- **Precision@10 by 7.97%**
- **F1@10 by 7.97%**
- **MRR@10 by 7.60%**

At depth 100, **Recall@100 improved by 1.73%**.

For users, the practical result is straightforward: more known-relevant passages appear near the top of the lexical ranking, where they are most likely to be selected, reranked, fused with vector results, or passed to a RAG system or AI agent.

## Why English Is an Important Test

German makes the value of linguistics relatively easy to see. Inflection is richer, compounds are pervasive, and irregular word forms often look very different from one another.

English is often thought to be different. Search systems have used English stemmers for decades, and English morphology is often treated as simple enough that more precise lexical analysis is unnecessary.

But English is not morphology-free. A suffix stemmer does not reliably connect irregular forms such as:

- **sell** and **sold**
- **come** and **came**
- **build** and **built**
- **make** and **made**

Stemming can also go too far, and this is probably the main issue with stemming and accuracy: it merges lexical items that are semantically unrelated, as in:

- **United** is stemmed to **unit**, merging **United** with unrelated words like **units**
- **Customs** is stemmed to **custom**, merging **Customs** with unrelated words like **customer** or **customize**

Stemming is also applied to proper names and titles, generating stems that mix unrelated words with brand names, as in:

- **Booking** becoming related to **book**
- **Progressive** becoming related to **progress**

Named entities add more problems when they contain more than one word. A typical example is **General Motors**, which is stemmed to **gener motor**, merging **General** with unrelated words like **generation** or **generous**.

A useful analyzer should not treat every capitalized word as an entity, since many are first words in sentences; but it should not blindly reduce every entity component to an ordinary-word stem either. This benchmark tests whether a linguistically informed analyzer can handle those distinctions well enough to improve actual retrieval.

## The Benchmark Data

The evaluation uses the public English development split of MIRACL, a multilingual monolingual-retrieval benchmark built from Wikipedia passages and human relevance assessments.

The final benchmark contains:

- **32,893,221** English Wikipedia passages
- **799** English queries
- **8,350** original MIRACL relevance judgments

All three configurations use the same corpus, queries, judgments, Elasticsearch version, BM25 parameters, index shape, retrieval depth, and evaluation procedure. The only intended difference is text analysis.

We focus on the first ten results because that is the part of the ranking most relevant to interactive search, reranking, hybrid fusion, RAG candidate selection, and agentic retrieval.

**Methodological note.** MIRACL, like other pooled information-retrieval benchmarks, does not judge every retrieved query-passage pair. Unjudged passages receive zero relevance credit in the canonical evaluation while remaining at their returned ranks.

## The Benchmark Setup

Every system uses:

- Elasticsearch 9.5.4
- BM25 with the default values of **k1 = 1.2** and **b = 0.75**
- One primary shard and no replicas
- Identical indexed title and passage fields
- The same 799 query set
- The same official NIST `trec_eval` scoring procedure and query population

No vector model, reranker, LLM, query expansion system, or learned retrieval component is involved. This isolates the effect of lexical text analysis.

## The Three Approaches to English Text Analysis

### Approach 1: Elasticsearch Standard

Elasticsearch’s default standard analyzer performs Unicode-aware tokenization and lowercasing, but no English stemming or lemmatization. This preserves surface distinctions, but misses many useful morphological relationships.

### Approach 2: Elasticsearch English

Elasticsearch’s built-in English analyzer adds:

- English possessive normalization
- Lowercasing
- English stopword removal
- Porter stemming

This improves lexical recall over standard analysis, but Porter stemming is algorithmic and suffix-oriented. It produces stems rather than dictionary lemmas, so it can miss irregular relationships and sometimes collapse terms too aggressively.

### Approach 3: Bitext English

Bitext English builds on the same general pipeline, while replacing and reordering several steps:

- Sentence-aware tokenization adds the context needed for better case and named-entity handling
- English possessive normalization is retained
- Lowercasing is deferred until after lexical and named-entity decisions have been made
- Porter stemming is replaced with dictionary-based lemmatization, while preserving the original word form for stronger exact matching
- Contextual named-entity handling protects terms from inappropriate ordinary-word normalization
- Duplicate removal removes redundant output when original forms and lemmas converge
- English stopword removal is retained

The sentence-aware logic matters because capitalization is ambiguous. At the start of a sentence, **Children** may simply be the plural of **child**. In **Save the Children**, the same form is part of a name and should remain protected. Bitext uses sentence position and local entity context to make that distinction without requiring a full named-entity extraction model at query time.

## The Results

| Configuration | nDCG@10 | Recall@10 | Recall@100 | Precision@10 | F1@10 | MRR@10 |
|---|---:|---:|---:|---:|---:|---:|
| Approach 1 – Elasticsearch Standard | 0.250600 | 0.321200 | 0.644800 | 0.089400 | 0.129218 | 0.304500 |
| Approach 2 – Elasticsearch English | 0.267200 | 0.347600 | 0.727700 | 0.099100 | 0.142206 | 0.322300 |
| **Approach 3 – Bitext Linguistic Analysis** | **0.290000** | **0.373900** | **0.740300** | **0.107000** | **0.153541** | **0.346800** |

Meaning of the metrics:

- **nDCG@10** measures ranking quality in the first ten results and rewards systems that place known-relevant passages higher
- **Recall@10** measures how much of the known-relevant material appears on the first result page
- **Recall@100** measures how much of the known-relevant material appears in the first hundred results
- **Precision@10** measures the proportion of the first ten results that is known relevant
- **F1@10** balances per-query first-page precision and recall
- **MRR@10** measures how early the first known-relevant passage appears, with evaluation capped at rank 10

Bitext produced the best result on every reported top-10 metric.

| Comparison | nDCG@10 | Recall@10 | Recall@100 | Precision@10 | F1@10 | MRR@10 |
|---|---:|---:|---:|---:|---:|---:|
| **Bitext English vs Elasticsearch Standard** | **+15.72%** | **+16.41%** | **+14.81%** | **+19.69%** | **+18.82%** | **+13.89%** |
| Bitext English vs Elasticsearch English | +8.53% | +7.57% | +1.73% | +7.97% | +7.97% | +7.60% |

The Elasticsearch English configuration clearly improves over Elasticsearch Standard analysis. That confirms that English morphology matters. Bitext English then improves again over the stemmer by replacing approximate stems with dictionary lemmas and adding contextual entity treatment.

## Examples of Recurring Issues that Bitext English Solves

The examples show several recurring advantages of using linguistic knowledge. See the companion examples file:

- [`english-examples.md`](english-examples.md)

The main issues are:

### Avoiding Over-Stemming

A stemmer may improve recall by conflating terms, but the conflation is not always linguistically sound. For example, the Porter stemmer reduces **majority** to **major**. Bitext preserves the complete word **majority**, keeping its specific lexical identity instead of merging it with a broader adjective and noun.

### Handling Irregular Morphology

Bitext connects dictionary forms that suffix stemming misses:

- **meaning / meant → mean**
- **sell / sold → sell**
- **make / made → make**
- **come / came → come**

These are ordinary English relationships, not rare linguistic curiosities. When the query and passage use different irregular forms, a stemmer may leave them disconnected.

### Preserving Names and Titles

Named entities are often built from ordinary words. **General** and **Motors** are morphologically analyzable in isolation, but in **General Motors** they are parts of a brand name. The sentence-aware Bitext analyzer preserves the brand name terms in context instead of reducing them to stems such as **gener** and **motor**.

Organizations, products, policies, locations, and technical names often contain words that an ordinary stemmer would transform.

## Relevance for RAG and AI-Based Agents

A search analyzer has to make decisions about morphology, possessives, and names before BM25, vector fusion, reranking, or generation can do anything with the text. If those decisions discard useful relationships or introduce noisy conflations, every downstream stage starts from weaker evidence.

A stronger lexical layer has impact at different levels:

- **Lexical search:** more relevant passages appear near the top of the result page
- **Hybrid retrieval:** the sparse channel contributes better candidates and better exact-term evidence before fusion with embeddings
- **RAG:** rerankers and language models receive stronger passages to ground the answer
- **AI agents:** exact names, titles, terminology, and irregular word forms are less likely to prevent retrieval of the required source

To avoid potential confusion: this benchmark does not claim that linguistic analysis replaces vector retrieval, reranking, or LLM reasoning. It shows that those systems benefit from a stronger lexical foundation. Named entities are particularly important to that complementarity. Semantic models are useful for conceptual similarity; lexical retrieval remains valuable for exact identities, rare names, titles, products, organizations, and terminology.

A hybrid system benefits when its lexical analyzer preserves those distinctions instead of turning them into generic stems.

## Conclusion

English is often treated as the language where generic stemming is enough. This benchmark suggests otherwise. Across 32.9 million passages and 799 MIRACL queries, Bitext’s linguistically informed English analyzer produced the strongest top-ranked lexical retrieval results:

- **15.72% higher nDCG@10** than Elasticsearch Standard
- **16.41% higher Recall@10**
- **19.69% higher Precision@10**
- **18.82% higher F1@10**
- **13.89% higher MRR@10**
- **14.81% higher Recall@100**

The gains come from treating language as language: normalizing possessives, connecting irregular forms through dictionary lemmas, preserving useful surface terms, and using context to avoid damaging names and titles.

For lexical search, that means better first-page results. For hybrid and RAG systems, it means a stronger sparse channel and better candidates before expensive downstream processing begins.

## Reproducing the Results

The scripts, configuration, and Bitext Elasticsearch plugin needed to reproduce the current English benchmark are included in this repository. See the [repository README](../README.md) for the published results and the [reproduction guide](reproduction.md) for the complete workflow.
