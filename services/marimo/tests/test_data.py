from uuid import UUID

from ellf_notebook import data


def test_sample_rows_have_the_shape_the_notebook_expects():
    examples = data.load_sample()
    assert examples.is_sample
    assert len(examples.rows) > 10
    row = examples.rows[0]
    for key in ("text", "spans", "answer", "_annotator_id", "_timestamp"):
        assert key in row


def test_missing_dataset_name_falls_back_and_says_why():
    examples = data.load_examples("")
    assert examples.is_sample
    assert examples.error


def test_unreadable_dataset_falls_back_and_says_why(monkeypatch):
    """A dataset that doesn't exist must not take the whole page down."""

    class _DB:
        def get_dataset_examples(self, name):
            raise RuntimeError("no such dataset")

    import prodigy.components.db as prodigy_db

    monkeypatch.setattr(prodigy_db, "connect", lambda *a, **kw: _DB())
    examples = data.load_examples("nope")
    assert examples.is_sample
    assert "no such dataset" in examples.error


def test_real_rows_are_marked_as_real(monkeypatch):
    class _DB:
        def get_dataset_examples(self, name):
            return [{"text": "hi", "answer": "accept"}]

    import prodigy.components.db as prodigy_db

    monkeypatch.setattr(prodigy_db, "connect", lambda *a, **kw: _DB())
    examples = data.load_examples("real")
    assert not examples.is_sample
    assert examples.dataset == "real"
    assert examples.rows == [{"text": "hi", "answer": "accept"}]


def test_configured_dataset_reads_the_env_var(monkeypatch):
    monkeypatch.setenv(data.DATASET_ENV_VAR, "support_ner")
    assert data.configured_dataset() == "support_ner"


def test_no_client_without_job_credentials(monkeypatch):
    monkeypatch.delenv("ELLF_PAM_BOOTSTRAP_TOKEN", raising=False)
    monkeypatch.delenv("ELLF_JOB_TOKEN", raising=False)
    monkeypatch.delenv("ELLF_PAM_HOST", raising=False)
    assert data.pam_client() is None


CLUSTER_ID = UUID("391f01d7-6ba0-520c-a4f1-5912e2a9f917")


class _FakeAsset:
    def __init__(self, name, kind, path):
        self.name = name
        self.kind = kind
        self.path = path
        self.version = "0.1.0"
        self.created = "2026-01-01"
        self.meta = {}
        self.id = "01a0-fake"


class _FakeResource:
    def __init__(self, rows):
        self.rows = rows
        self.queries = []

    def all(self, query):
        self.queries.append(query)
        return list(self.rows)


class _FakeClient:
    def __init__(self, assets=(), tasks=(), actions=()):
        self.asset = _FakeResource(assets)
        self.task = _FakeResource(tasks)
        self.action = _FakeResource(actions)


def test_cluster_assets_returns_the_columns_the_notebooks_read():
    client = _FakeClient(assets=[_FakeAsset("m", "model", "/mnt/nfs/data/m")])
    rows = data.cluster_assets(client, CLUSTER_ID)
    assert rows == [
        {
            "name": "m",
            "kind": "model",
            "version": "0.1.0",
            "path": "/mnt/nfs/data/m",
            "created": "2026-01-01",
            "meta": {},
            "id": "01a0-fake",
        }
    ]


def test_cluster_assets_passes_the_kind_filter_through():
    client = _FakeClient(assets=[])
    data.cluster_assets(client, CLUSTER_ID, kind="results")
    assert client.asset.queries[0].kind == "results"


def test_cluster_assets_without_a_kind_does_not_filter():
    client = _FakeClient(assets=[])
    data.cluster_assets(client, CLUSTER_ID)
    assert client.asset.queries[0].kind is None


def test_load_json_asset_reads_the_file_at_the_asset_path(tmp_path):
    path = tmp_path / "model.results.json"
    path.write_text('{"performance": {"ents_f": 0.5}}', encoding="utf8")
    assert data.load_json_asset(str(path))["performance"]["ents_f"] == 0.5


def test_cluster_jobs_merges_tasks_and_actions_newest_first():
    class _Job:
        def __init__(self, name, created, **extra):
            self.name = name
            self.created = created
            self.job_type = "task"
            self.id = "01a0-job"
            self.recipe_name = extra.get("recipe_name", "")
            self.project_name = extra.get("project_name", "")

    client = _FakeClient(
        tasks=[_Job("older", "2026-01-01", recipe_name="ner")],
        actions=[_Job("newer", "2026-02-01")],
    )
    rows = data.cluster_jobs(client, CLUSTER_ID)
    assert [row["name"] for row in rows] == ["newer", "older"]


def test_a_stored_alias_is_resolved_to_a_real_path(monkeypatch):
    """The platform stores whatever was typed, often `{__nfs__}/...`.

    The broker expands those only for objects passed into a recipe. An asset
    fetched at runtime through the SDK comes back raw, so reading one means
    resolving it here first.
    """
    monkeypatch.setenv("ELLF_BUILTIN_PATH_NFS", "/mnt/nfs")
    assert data.resolve_path("{__nfs__}/models/run.json") == "/mnt/nfs/models/run.json"


def test_an_absolute_path_is_left_alone(monkeypatch):
    monkeypatch.setenv("ELLF_BUILTIN_PATH_NFS", "/mnt/nfs")
    assert data.resolve_path("/mnt/nfs/models/run.json") == "/mnt/nfs/models/run.json"


def test_an_unresolvable_alias_is_returned_unchanged(monkeypatch):
    """Off-cluster there is no mount, so failing loudly beats a silent read."""
    monkeypatch.delenv("ELLF_BUILTIN_PATH_NFS", raising=False)
    assert data.resolve_path("{__nfs__}/models/run.json") == "{__nfs__}/models/run.json"


def test_asset_paths_come_back_resolved(monkeypatch):
    monkeypatch.setenv("ELLF_BUILTIN_PATH_NFS", "/mnt/nfs")
    client = _FakeClient(assets=[_FakeAsset("run", "results", "{__nfs__}/models/run.json")])
    assert data.cluster_assets(client, CLUSTER_ID)[0]["path"] == "/mnt/nfs/models/run.json"
