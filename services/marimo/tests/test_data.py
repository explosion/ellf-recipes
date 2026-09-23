import sys
from types import ModuleType
from uuid import UUID

from ellf_notebook import data

CLUSTER_ID = UUID("391f01d7-6ba0-520c-a4f1-5912e2a9f917")


def _fake_prodigy_db(monkeypatch, db):
    """Stand in for the Prodigy database, so the tests don't need Prodigy."""
    module = ModuleType("prodigy.components.db")
    module.connect = lambda *args, **kwargs: db
    monkeypatch.setitem(sys.modules, "prodigy.components.db", module)


def test_load_examples_returns_the_rows(monkeypatch):
    class _DB:
        def get_dataset_examples(self, name):
            return [{"text": "hi", "answer": "accept"}]

    _fake_prodigy_db(monkeypatch, _DB())
    examples = data.load_examples("real")
    assert not examples.failed
    assert examples.rows == [{"text": "hi", "answer": "accept"}]


def test_load_examples_returns_the_error_instead_of_raising(monkeypatch):
    class _DB:
        def get_dataset_examples(self, name):
            raise RuntimeError("no such dataset")

    _fake_prodigy_db(monkeypatch, _DB())
    examples = data.load_examples("missing")
    assert examples.failed
    assert examples.rows == []
    assert "no such dataset" in examples.error


def test_cluster_assets_resolves_custom_path_aliases():
    """The `train` recipe saves models to `{models}/<name>` by default."""

    class _Asset:
        name = "run.results"
        kind = "results"
        version = "0.1.0"
        path = "{models}/run.results.json"
        created = "2026-01-01"
        meta = {}
        id = "asset-id"

    class _Assets:
        def all(self, query):
            return [_Asset()]

    class _ClusterPaths:
        def read(self, query):
            assert query.name == "models"
            return type("ClusterPath", (), {"path": "/mnt/nfs/models"})()

    class _Client:
        asset = _Assets()
        cluster_path = _ClusterPaths()

    rows = data.cluster_assets(_Client(), CLUSTER_ID)
    assert rows[0]["path"] == "/mnt/nfs/models/run.results.json"


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
    assert info["datasets"] == {"ner": ["support_ner"]}
    assert info["eval_datasets"] == {"ner": ["support_ner_eval"]}
