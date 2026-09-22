import pytest

from ellf_notebook import workspace


@pytest.fixture
def root(tmp_path, monkeypatch):
    monkeypatch.setenv(workspace.ROOT_ENV_VAR, str(tmp_path))
    return tmp_path


def test_workspace_root_prefers_override(root):
    assert workspace.workspace_root() == root


def test_workspace_root_falls_back_to_nfs(tmp_path, monkeypatch):
    monkeypatch.delenv(workspace.ROOT_ENV_VAR, raising=False)
    monkeypatch.setenv(workspace.NFS_ENV_VAR, str(tmp_path))
    assert workspace.workspace_root() == tmp_path / workspace.NFS_SUBDIR


def test_resolve_workspace_creates_the_directory(root):
    directory = workspace.resolve_workspace("team-a")
    assert directory == root / "team-a"
    assert directory.is_dir()


@pytest.mark.parametrize("name", ["../escape", "a/b", "", "with space", "..", "a.b"])
def test_workspace_names_that_would_escape_the_root_are_rejected(root, name):
    with pytest.raises(ValueError):
        workspace.resolve_workspace(name)


@pytest.mark.parametrize(
    "name", ["../evil.py", "sub/dir.py", "notebook.txt", "notebook", ".py"]
)
def test_notebook_names_are_validated(name):
    with pytest.raises(ValueError):
        workspace.validate_notebook(name)


def test_seed_notebook_copies_the_bundled_starter(root):
    directory = workspace.resolve_workspace("w")
    path = workspace.seed_notebook(directory, workspace.DEFAULT_NOTEBOOK)
    assert path == directory / workspace.DEFAULT_NOTEBOOK
    assert "marimo.App" in path.read_text(encoding="utf8")


def test_seed_notebook_never_overwrites_an_edited_notebook(root):
    directory = workspace.resolve_workspace("w")
    path = workspace.seed_notebook(directory, workspace.DEFAULT_NOTEBOOK)
    path.write_text("# my edits\n", encoding="utf8")
    assert workspace.seed_notebook(directory, workspace.DEFAULT_NOTEBOOK) == path
    assert path.read_text(encoding="utf8") == "# my edits\n"


def test_an_unknown_notebook_name_starts_from_the_blank_template(root):
    directory = workspace.resolve_workspace("w")
    path = workspace.seed_notebook(directory, "my_analysis.py")
    assert path.exists()
    assert path.read_text(encoding="utf8") == (
        workspace._templates_dir() / "blank.py"
    ).read_text(encoding="utf8")


def test_bundled_notebooks_are_listed(root):
    assert workspace.DEFAULT_NOTEBOOK in workspace.bundled_notebooks()
    assert "blank.py" in workspace.bundled_notebooks()
