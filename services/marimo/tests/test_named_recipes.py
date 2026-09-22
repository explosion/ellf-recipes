"""The named recipes open their own notebook and pass their own inputs.

These exist because the whole point of splitting them out was that each asks
for what its notebook needs. A regression here would look like a working
service that quietly opens the wrong thing.
"""

import uuid

import pytest

from ellf_recipes_sdk import InputDataset, Model

from ellf_notebook import launcher, workspace
from ellf_notebook.recipes import dataset_explorer, training_results


@pytest.fixture
def launched(tmp_path, monkeypatch):
    """Run a recipe with the marimo launch captured instead of executed."""
    monkeypatch.setenv(workspace.ROOT_ENV_VAR, str(tmp_path))
    calls = []

    def fake_popen(argv, **kwargs):
        calls.append((argv, kwargs))
        return None

    monkeypatch.setattr(launcher.subprocess, "Popen", fake_popen)
    return calls


def _dataset(name="support_ner"):
    return InputDataset(id=uuid.uuid4(), name=name, cluster_id=uuid.uuid4())


def _model(name="ner_v1", path="/mnt/nfs/data/models/ner_v1", meta=None):
    return Model(
        id=uuid.uuid4(),
        cluster_id=uuid.uuid4(),
        name=name,
        version="0.1.0",
        path=path,
        meta=meta or {},
    )


def test_dataset_explorer_opens_its_own_notebook(launched, tmp_path):
    assert dataset_explorer.dataset_explorer(dataset=_dataset()) is None
    argv, kwargs = launched[0]
    notebook = tmp_path / workspace.DEFAULT_WORKSPACE / "dataset_explorer.py"
    assert notebook.exists()
    assert str(notebook) in argv
    assert kwargs["env"]["ELLF_MARIMO_DATASET"] == "support_ner"


def test_training_results_opens_its_own_notebook(launched, tmp_path):
    assert training_results.training_results(dataset=_dataset(), model=_model()) is None
    argv, kwargs = launched[0]
    notebook = tmp_path / workspace.DEFAULT_WORKSPACE / "training_results.py"
    assert notebook.exists()
    assert str(notebook) in argv


def test_a_directory_model_is_loaded_by_path(launched):
    training_results.training_results(
        dataset=_dataset(), model=_model(path="/mnt/nfs/data/models/ner_v1")
    )
    env = launched[0][1]["env"]
    assert env["ELLF_MARIMO_MODEL"] == "ner_v1"
    assert env["ELLF_MARIMO_MODEL_TARGET"] == "/mnt/nfs/data/models/ner_v1"


def test_a_packaged_model_is_loaded_by_its_spacy_name(launched):
    """A wheel is pip-installed before Python starts, so a path won't load it."""
    training_results.training_results(
        dataset=_dataset(),
        model=_model(
            path="/mnt/nfs/data/models/ner_v1.whl",
            meta={"format": "package", "spacy_model_name": "en_ner_v1"},
        ),
    )
    env = launched[0][1]["env"]
    assert env["ELLF_MARIMO_MODEL_TARGET"] == "en_ner_v1"


def test_the_named_recipes_share_one_launcher(launched):
    """Both go through `launch`, so neither can drift on flags or cwd."""
    dataset_explorer.dataset_explorer(dataset=_dataset())
    training_results.training_results(dataset=_dataset(), model=_model())
    first, second = launched
    assert first[0][1:3] == second[0][1:3] == ["-m", "marimo"]
    for argv, _ in launched:
        assert "--headless" in argv and "--no-token" in argv
