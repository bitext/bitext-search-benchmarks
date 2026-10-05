import importlib.util
import io
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch


MODULE = Path(__file__).resolve().parents[1] / "benchmark.py"
SPEC = importlib.util.spec_from_file_location("benchmark", MODULE)
benchmark = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(benchmark)


class BenchmarkTests(unittest.TestCase):
    def test_public_configuration_and_depth_are_pinned(self):
        self.assertEqual(benchmark.CONFIG["elasticsearch_version"], "9.5.4")
        self.assertEqual(benchmark.CONFIG["bm25"], {"k1": 1.2, "b": 0.75})
        self.assertEqual(benchmark.RETRIEVAL_DEPTH, 100)
        self.assertEqual(benchmark.MRR_CUTOFF, 10)
        self.assertEqual(benchmark.CONFIG["trec_eval"]["version"], "9.0.8")
        self.assertEqual(benchmark.CONFIG["trec_eval"]["revision"], "d4dd9d9ca4b7984fc48788052503cc4d1644c529")
        self.assertEqual(
            benchmark.trec_eval_source_directory(),
            benchmark.ROOT / "data" / "tools" / "trec_eval" / benchmark.CONFIG["trec_eval"]["revision"] / "source",
        )

    def test_three_arms_and_minimal_public_bitext_configuration(self):
        self.assertEqual(benchmark.ARMS["standard"], "standard")
        self.assertEqual(benchmark.ARMS["elastic-english"], "english")
        body = benchmark.index_body(benchmark.ARMS["bitext-english"])
        self.assertEqual(
            body["settings"]["analysis"]["analyzer"][benchmark.ARMS["bitext-english"]],
            {"type": "bitext_java_english"},
        )

    def test_f1_uses_official_per_query_precision_and_recall(self):
        values = {("P_10", "q1"): 0.1, ("recall_10", "q1"): 1.0, ("P_10", "q2"): 0.0, ("recall_10", "q2"): 0.0}
        self.assertAlmostEqual(benchmark.macro_f1(values, ["q1", "q2"]), 1 / 11)

    def test_official_measure_names_include_recall_at_one_hundred(self):
        self.assertEqual(benchmark.TREC_EVAL_MEASURES, ("ndcg_cut.10", "P.10", "recall.10,100"))
        parsed = benchmark.parse_trec_eval("P_10 all 0.1\nrecall_10 all 0.2\nrecall_100 all 0.3\n")
        self.assertEqual(parsed[("recall_100", "all")], 0.3)

    def test_run_validation_requires_one_hundred_results_per_query(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory) / "run.trec"
            run.write_text("".join(f"q1 Q0 d{rank} {rank} 1.0 arm\n" for rank in range(1, 101)), encoding="utf-8")
            benchmark.validate_run([("q1", "one")], run)

    def test_test_run_validation_allows_fewer_than_requested_depth(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory) / "run.trec"
            run.write_text("".join(f"q1 Q0 d{rank} {rank} 1.0 arm\n" for rank in range(1, 25)), encoding="utf-8")
            benchmark.validate_run([("q1", "one")], run, require_full_depth=False)
            with self.assertRaises(ValueError):
                benchmark.validate_run([("q1", "one")], run)

    def test_qrels_driven_test_fixture_is_complete_and_deterministic(self):
        topic_count = int(benchmark.CONFIG["miracl"]["test_queries"])
        corpus_size = int(benchmark.CONFIG["miracl"]["test_documents"])
        topics = [(f"q{number}", f"query {number}") for number in range(topic_count)]
        qrels = {qid: {f"p{number}": 1} for number, (qid, _query) in enumerate(topics)}
        candidates = [{"docid": f"p{number}", "text": "judged"} for number in range(topic_count)]
        candidates += [{"docid": f"d{number}", "text": "distractor"} for number in range(corpus_size - topic_count)]
        available = {document["docid"] for document in candidates}

        selected, positives = benchmark.select_test_topics(topics, qrels, available)
        again, again_positives = benchmark.select_test_topics(topics, qrels, available)
        corpus = benchmark.build_test_corpus(candidates, positives)

        self.assertEqual((selected, positives), (again, again_positives))
        self.assertEqual(len(selected), topic_count)
        self.assertTrue(all(benchmark.positive_qrel_documents(qrels, qid) for qid, _query in selected))
        self.assertTrue(all(benchmark.positive_qrel_documents(qrels, qid) <= {doc["docid"] for doc in corpus} for qid, _query in selected))
        self.assertEqual(len(corpus), corpus_size)
        self.assertEqual(len({document["docid"] for document in corpus}), corpus_size)

    def test_report_includes_recall_at_one_hundred(self):
        scores = {arm: {"nDCG@10": 0.2, "Recall@10": 0.3, "Recall@100": 0.4, "Precision@10": 0.1, "F1@10": 0.15, "MRR@10": 0.25} for arm in benchmark.ARMS}
        with tempfile.TemporaryDirectory() as directory:
            result = Path(directory)
            benchmark.write_report(result, "test", scores, [])
            report = (result / "benchmark.md").read_text(encoding="utf-8")
            self.assertIn("Recall@100", report)
            self.assertIn("| Elasticsearch Standard |", report)
            self.assertIn("| Elasticsearch English |", report)
            self.assertIn("| Bitext English Analyzer |", report)

    def test_trec_rank_validation_rejects_gaps(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory) / "run.trec"
            run.write_text("q1 Q0 a 2 1.0 arm\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                benchmark.validate_run([("q1", "one")], run)

    def test_failed_captured_build_prints_diagnostics(self):
        completed = subprocess.CompletedProcess(["make"], 1, "compiler output\n", "compiler error\n")
        diagnostics = io.StringIO()
        with patch.object(benchmark.subprocess, "run", return_value=completed), redirect_stderr(diagnostics):
            with self.assertRaisesRegex(RuntimeError, "failed to build trec_eval"):
                benchmark.run_captured(["make"], "build trec_eval")
        self.assertIn("compiler output", diagnostics.getvalue())
        self.assertIn("compiler error", diagnostics.getvalue())

    def test_docker_daemon_failure_has_actionable_message(self):
        completed = subprocess.CompletedProcess(["docker", "info"], 1, "", "cannot connect")
        with patch.object(benchmark.subprocess, "run", return_value=completed):
            with self.assertRaisesRegex(RuntimeError, "Docker daemon is not running"):
                benchmark.require_docker_daemon()

    def test_failed_captured_docker_command_prints_diagnostics(self):
        completed = subprocess.CompletedProcess(["docker", "compose"], 1, "build output\n", "compose error\n")
        diagnostics = io.StringIO()
        with patch.object(benchmark.subprocess, "run", return_value=completed), redirect_stderr(diagnostics):
            with self.assertRaisesRegex(RuntimeError, "failed to build and start Elasticsearch"):
                benchmark.run_captured(["docker", "compose"], "build and start Elasticsearch")
        self.assertIn("build output", diagnostics.getvalue())
        self.assertIn("compose error", diagnostics.getvalue())


if __name__ == "__main__":
    unittest.main()
