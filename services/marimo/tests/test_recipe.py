import uuid

import pytest

from ellf_recipes_sdk import InputDataset

from ellf_notebook import launcher, workspace
from ellf_notebook.recipes import marimo_notebook as recipe


@pytest.fixture
def launched(tmp_path, monkeypatch):
    """Run the recipe with the marimo launch captured instead of executed."""
    monkeypatch.setenv(workspace.ROOT_ENV_VAR, str(tmp_path))
    calls = []

    def fake_popen(argv, **kwargs):
        calls.append((argv, kwargs))
        return None

    monkeypatch.setattr(launcher.subprocess, "Popen", fake_popen)
    return calls


def _run(**kwargs):
    dataset = InputDataset(id=uuid.uuid4(), name="support_ner", cluster_id=uuid.uuid4())
    return recipe.marimo_notebook(dataset=dataset, **kwargs)


def test_it_opens_the_workspace_rather_than_one_notebook(launched, tmp_path):
    """No filename means marimo's home page, which lists the workspace."""
    assert _run() is None
    (argv, kwargs) = launched[0]
    workspace_dir = tmp_path / workspace.DEFAULT_WORKSPACE
    assert argv[1:3] == ["-m", "marimo"]
    assert "edit" in argv
    assert not [a for a in argv if a.endswith(".py")]
    assert "--headless" in argv and "--no-token" in argv
    assert argv[argv.index("--host") + 1] == "0.0.0.0"
    # cwd is the workspace, so the home page lists it and files land there
    assert kwargs["cwd"] == str(workspace_dir)


def test_an_empty_workspace_gets_one_notebook_to_open(launched, tmp_path):
    """An empty home page would be a dead end on a brand new workspace."""
    _run()
    seeded = tmp_path / workspace.DEFAULT_WORKSPACE / launcher.FALLBACK_NOTEBOOK
    assert seeded.exists()


def test_an_existing_workspace_is_left_alone(launched, tmp_path):
    """Seeding into a workspace people already use would be an intrusion."""
    workspace_dir = tmp_path / workspace.DEFAULT_WORKSPACE
    workspace_dir.mkdir(parents=True)
    (workspace_dir / "theirs.py").write_text("import marimo\n", encoding="utf8")
    _run()
    assert not (workspace_dir / launcher.FALLBACK_NOTEBOOK).exists()
    assert sorted(p.name for p in workspace_dir.glob("*.py")) == ["theirs.py"]


def test_read_only_without_a_notebook_is_refused():
    """`marimo run` serves one notebook, so a workspace cannot be an app."""
    with pytest.raises(ValueError):
        launcher.launch(workspace="w", read_only=True)


def test_read_only_serves_the_app_instead_of_the_editor(launched):
    launcher.launch(workspace="w", notebook="blank.py", read_only=True)
    argv = launched[0][0]
    assert "run" in argv and "edit" not in argv
    assert "--include-code" in argv


def test_it_binds_the_port_the_cluster_probes(launched, monkeypatch):
    monkeypatch.setenv("ELLF_RECIPES_PORT", "9000")
    _run()
    argv = launched[0][0]
    assert argv[argv.index("--port") + 1] == "9000"


def test_it_defaults_to_marimos_own_port(launched, monkeypatch):
    monkeypatch.delenv("ELLF_RECIPES_PORT", raising=False)
    _run()
    argv = launched[0][0]
    assert argv[argv.index("--port") + 1] == str(launcher.MARIMO_PORT)
    # The declared port and the bound port must not drift: the cluster routes
    # and health-checks whatever @service_recipe declared.
    assert launcher.MARIMO_PORT == 2718


def test_marimo_settings_are_kept_in_the_workspace(launched, tmp_path):
    """Not in $HOME: the pod's home need not be writable, and settings persist."""
    _run(workspace="team-a")
    env = launched[0][1]["env"]
    expected = str(tmp_path / "team-a" / ".marimo")
    assert env["XDG_CONFIG_HOME"] == expected
    assert env["XDG_CACHE_HOME"] == expected
    assert env["XDG_STATE_HOME"] == expected


def test_the_notebook_process_is_told_which_dataset_to_open(launched):
    _run()
    env = launched[0][1]["env"]
    assert env["ELLF_MARIMO_DATASET"] == "support_ner"


def test_a_second_service_on_the_same_workspace_keeps_the_edits(launched, tmp_path):
    launcher.launch(workspace="shared", notebook="blank.py")
    notebook = tmp_path / "shared" / "blank.py"
    notebook.write_text("# edited in the browser\n", encoding="utf8")
    launcher.launch(workspace="shared", notebook="blank.py")
    assert notebook.read_text(encoding="utf8") == "# edited in the browser\n"
