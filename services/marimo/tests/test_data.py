from uuid import UUID

import prodigy.components.db as prodigy_db

from ellf_notebook import data

CLUSTER_ID = UUID("391f01d7-6ba0-520c-a4f1-5912e2a9f917")


def test_load_examples_returns_the_rows(monkeypatch):
    class _DB:
        def get_dataset_examples(self, name):
            return [{"text": "hi", "answer": "accept"}]

    monkeypatch.setattr(prodigy_db, "connect", lambda *a, **kw: _DB())
    examples = data.load_examples("real")
    assert not examples.failed
    assert examples.rows == [{"text": "hi", "answer": "accept"}]


def test_load_examples_returns_the_error_instead_of_raising(monkeypatch):
    class _DB:
        def get_dataset_examples(self, name):
            raise RuntimeError("no such dataset")

    monkeypatch.setattr(prodigy_db, "connect", lambda *a, **kw: _DB())
    examples = data.load_examples("missing")
    assert examples.failed
    assert examples.rows == []
    assert "no such dataset" in examples.error


def test_cluster_assets_resolves_path_aliases(monkeypatch):
    class _Asset:
        name = "run"
        kind = "results"
        version = "0.1.0"
        path = "{__nfs__}/models/run.json"
        created = "2026-01-01"
        meta = {}
        id = "asset-id"

    class _Assets:
        def all(self, query):
            return [_Asset()]

    class _Client:
        asset = _Assets()

    monkeypatch.setenv("ELLF_BUILTIN_PATH_NFS", "/mnt/nfs")
    rows = data.cluster_assets(_Client(), CLUSTER_ID)
    assert rows[0]["path"] == "/mnt/nfs/models/run.json"


def test_training_corpora_reads_the_datasets_from_the_model_config(tmp_path):
    (tmp_path / "config.cfg").write_text(
        """
[system]
seed = 0

[corpora]
@readers = "prodigy.MergedCorpus.v1"
eval_split = 0.2

[corpora.ner]
@readers = "prodigy.NERCorpus.v1"
datasets = ["support_ner"]
eval_datasets = ["support_ner_eval"]
""",
        encoding="utf8",
    )
    info = data.training_corpora(str(tmp_path))
    assert info["train_datasets"] == ["support_ner"]
    assert info["eval_datasets"] == ["support_ner_eval"]
