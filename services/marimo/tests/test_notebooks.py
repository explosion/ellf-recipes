"""The starter notebooks are shipped source, so they get the same scrutiny."""

import ast

import pytest

from ellf_notebook import workspace


def _notebook_paths():
    return sorted((workspace._templates_dir()).glob("*.py"))


@pytest.mark.parametrize("path", _notebook_paths(), ids=lambda p: p.name)
def test_starter_notebooks_are_valid_python(path):
    ast.parse(path.read_text(encoding="utf8"), filename=str(path))


@pytest.mark.parametrize("path", _notebook_paths(), ids=lambda p: p.name)
def test_starter_notebooks_are_marimo_notebooks(path):
    source = path.read_text(encoding="utf8")
    assert "marimo.App(" in source
    assert "@app.cell" in source
    # Without this, `marimo edit` opens the file but `python notebook.py`
    # silently does nothing.
    assert 'if __name__ == "__main__":' in source


def test_the_default_notebook_is_bundled():
    assert (workspace._templates_dir() / workspace.DEFAULT_NOTEBOOK).exists()


@pytest.mark.parametrize("path", _notebook_paths(), ids=lambda p: p.name)
def test_starter_notebooks_import_the_published_package_name(path):
    """The seeded copy on NFS keeps importing this name forever.

    A starter is copied into a workspace once and then diverges. Renaming the
    package would break every notebook anyone has edited since, so the name is
    pinned here deliberately: if this test fails, the fix is almost never to
    update the test.
    """
    source = path.read_text(encoding="utf8")
    if "import data" in source:
        assert "from ellf_notebook import data" in source
