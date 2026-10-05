#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
cd "$ROOT"

prepare_elasticsearch_data_dir() {
  local es_data_dir=${MIRACL_ES_DATA_DIR:-"$ROOT/data/elasticsearch"}
  if [[ $es_data_dir != /* ]]; then
    es_data_dir="$ROOT/$es_data_dir"
  fi
  mkdir -p "$es_data_dir"
  if [[ ! -d $es_data_dir || ! -w $es_data_dir || ! -x $es_data_dir ]]; then
    echo "Elasticsearch data directory is not usable: $es_data_dir" >&2
    echo "Choose a writable directory with MIRACL_ES_DATA_DIR=/path/to/elasticsearch." >&2
    exit 2
  fi
  MIRACL_ES_DATA_DIR=$(cd "$es_data_dir" && pwd -P)
  export MIRACL_ES_DATA_DIR
}

if [[ ${1:-} == --test ]]; then
  prepare_elasticsearch_data_dir
  exec python3 scripts/benchmark.py test
fi
if [[ ${1:-} == --full ]]; then
  prepare_elasticsearch_data_dir
  exec python3 scripts/benchmark.py full
fi
if [[ ${1:-} == --rescore ]]; then
  exec python3 scripts/benchmark.py rescore
fi

echo "Usage: $0 --test | --full | --rescore" >&2
echo "--test exercises the complete pipeline on a deterministic MIRACL subset." >&2
echo "--full runs the complete corpus and is restartable during indexing." >&2
echo "--rescore replaces scores for completed canonical runs without querying or indexing." >&2
exit 2
