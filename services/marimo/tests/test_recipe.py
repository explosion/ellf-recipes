"""The service runs a notebook asset, and edits the copy rather than the source."""

import uuid

import pytest

from ellf_notebook import launcher, workspace
from ellf_notebook.recipes import marimo_notebook as recipe
from ellf_notebook.types import Notebook

SOURCE_TEXT = "import marimo\n# the registered notebook\n"


@pytest.fixture
def source(tmp_path):
    """A notebook asset's file, standing in for one on shared storage."""
    starters = tmp_path / "starters"
    starters.mkdir()
    path = starters / "explorer.py"
    path.write_text(SOURCE_TEXT, encoding="utf8")
    return path


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


def _notebook(source, name="explorer"):
    return Notebook(
        id=uuid.uuid4(),
        cluster_id=uuid.uuid4(),
        name=name,
        version="0.1.0",
        path=str(source),
        meta={},
    )


def _run(source, **kwargs):
    return recipe.marimo_notebook(notebook=_notebook(source), **kwargs)


def test_it_opens_a_copy_seeded_from_the_asset(launched, source, tmp_path):
    assert _run(source) is None
    argv, kwargs = launched[0]
    copy = tmp_path / workspace.DEFAULT_WORKSPACE / "explorer.py"
    assert copy.exists()
    assert copy.read_text(encoding="utf8") == SOURCE_TEXT
    assert argv[1:3] == ["-m", "marimo"]
    assert "edit" in argv
    assert str(copy) in argv
    assert "--headless" in argv and "--no-token" in argv
    assert kwargs["cwd"] == str(copy.parent)


def test_the_asset_file_is_never_what_gets_edited(launched, source, tmp_path):
    """Two people opening one notebook must not write over each other."""
    _run(source)
    copy = tmp_path / workspace.DEFAULT_WORKSPACE / "explorer.py"
    assert copy != source
    assert str(source) not in launched[0][0]


def test_a_workspace_copy_survives_a_restart(launched, source, tmp_path):
    """The copy holds the user's edits, so seeding must not overwrite it."""
    _run(source, workspace="shared")
    copy = tmp_path / "shared" / "explorer.py"
    copy.write_text("# edited in the browser\n", encoding="utf8")
    _run(source, workspace="shared")
    assert copy.read_text(encoding="utf8") == "# edited in the browser\n"


def test_read_only_serves_the_app_instead_of_the_editor(launched, source):
    _run(source, read_only=True)
    argv = launched[0][0]
    assert "run" in argv and "edit" not in argv
    assert "--include-code" in argv


def test_it_binds_the_port_the_cluster_probes(launched, source, monkeypatch):
    monkeypatch.setenv("ELLF_RECIPES_PORT", "9000")
    _run(source)
    argv = launched[0][0]
    assert argv[argv.index("--port") + 1] == "9000"


def test_it_defaults_to_marimos_own_port(launched, source, monkeypatch):
    monkeypatch.delenv("ELLF_RECIPES_PORT", raising=False)
    _run(source)
    argv = launched[0][0]
    assert argv[argv.index("--port") + 1] == str(launcher.MARIMO_PORT)
    # The declared port and the bound port must not drift: the cluster routes
    # and health-checks whatever @service_recipe declared.
    assert launcher.MARIMO_PORT == 2718


def test_marimo_settings_are_kept_in_the_workspace(launched, source, tmp_path):
    """Not in $HOME: the pod's home need not be writable, and settings persist."""
    _run(source, workspace="team-a")
    env = launched[0][1]["env"]
    expected = str(tmp_path / "team-a" / ".marimo")
    assert env["XDG_CONFIG_HOME"] == expected
    assert env["XDG_CACHE_HOME"] == expected
    assert env["XDG_STATE_HOME"] == expected


def test_the_notebook_process_is_told_which_notebook_it_is(launched, source):
    _run(source)
    env = launched[0][1]["env"]
    assert env["ELLF_MARIMO_NOTEBOOK"] == "explorer"


def test_read_only_without_a_notebook_is_refused():
    """`marimo run` serves one notebook, so a workspace cannot be an app."""
    with pytest.raises(ValueError):
        launcher.launch(workspace="w", read_only=True)


def test_descriptions_fit_the_column_they_are_stored_in():
    """PAM stores these in a varchar(255) and nothing checks before the insert.

    Going over shows up as an opaque 500 from `ellf publish code`, after the
    package has already been created, so it is worth catching here.
    """
    import re
    from pathlib import Path

    recipes_dir = Path(__file__).resolve().parent.parent / "ellf_notebook"
    for path in recipes_dir.rglob("*.py"):
        source = path.read_text(encoding="utf8")
        for match in re.finditer(r'description=\(\s*((?:\s*"[^"]*"\s*)+)\)', source):
            text = "".join(re.findall(r'"([^"]*)"', match.group(1)))
            assert len(text) <= 255, f"{path.name}: {len(text)} chars"
