import re
import uuid
from pathlib import Path

import pytest

from ellf_notebook import launcher, workspace
from ellf_notebook.recipes import marimo_notebook as recipe
from ellf_notebook.types import Notebook

PACKAGE_DIR = Path(__file__).resolve().parent.parent / "ellf_notebook"
SOURCE_TEXT = "import marimo\n"


@pytest.fixture
def launched(tmp_path, monkeypatch):
    """Run the recipe with the marimo process recorded instead of started."""
    monkeypatch.setenv(workspace.ROOT_ENV_VAR, str(tmp_path / "workspaces"))
    calls = []
    monkeypatch.setattr(
        launcher.subprocess, "Popen", lambda argv, **kw: calls.append((argv, kw))
    )
    return calls


@pytest.fixture
def source(tmp_path):
    """The notebook asset's file on shared storage."""
    path = tmp_path / "explorer.py"
    path.write_text(SOURCE_TEXT, encoding="utf8")
    return path


def _run(source, **kwargs):
    notebook = Notebook(
        id=uuid.uuid4(),
        cluster_id=uuid.uuid4(),
        name="explorer",
        version="0.1.0",
        path=str(source),
        meta={},
    )
    return recipe.marimo_notebook(notebook=notebook, **kwargs)


def test_the_recipe_opens_a_copy_of_the_notebook(launched, source, tmp_path):
    assert _run(source) is None
    argv, kwargs = launched[0]
    copy = tmp_path / "workspaces" / workspace.DEFAULT_WORKSPACE / "explorer.py"
    assert copy.read_text(encoding="utf8") == SOURCE_TEXT
    assert "edit" in argv
    assert str(copy) in argv
    assert argv[argv.index("--port") + 1] == str(launcher.MARIMO_PORT)
    assert kwargs["cwd"] == str(copy.parent)


def test_the_working_copy_is_never_overwritten(launched, source, tmp_path):
    _run(source, workspace="shared")
    copy = tmp_path / "workspaces" / "shared" / "explorer.py"
    copy.write_text("# edited in the browser\n", encoding="utf8")
    _run(source, workspace="shared")
    assert copy.read_text(encoding="utf8") == "# edited in the browser\n"


@pytest.mark.parametrize("name", ["../escape", "a/b", "", "with space", ".."])
def test_workspace_names_outside_the_root_are_rejected(launched, name):
    with pytest.raises(ValueError):
        workspace.resolve_workspace(name)


@pytest.mark.parametrize(
    "path", sorted((PACKAGE_DIR / "notebooks").glob("*.py")), ids=lambda p: p.name
)
def test_the_included_notebooks_are_marimo_notebooks(path):
    source = path.read_text(encoding="utf8")
    compile(source, str(path), "exec")
    assert "marimo.App(" in source
    assert "from ellf_notebook import data" in source


def test_descriptions_fit_in_255_characters():
    """Longer descriptions make `ellf publish code` fail with a 500 error."""
    for path in PACKAGE_DIR.rglob("*.py"):
        source = path.read_text(encoding="utf8")
        for match in re.finditer(r'description=\(\s*((?:\s*"[^"]*"\s*)+)\)', source):
            text = "".join(re.findall(r'"([^"]*)"', match.group(1)))
            assert len(text) <= 255, f"{path.name}: {len(text)} characters"
