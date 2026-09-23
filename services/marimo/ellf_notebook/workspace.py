"""Where the working copies of notebooks are stored.

A marimo notebook is a Python file that users edit in the browser, so it can't
be stored in the container image, which is replaced when the pod restarts.
Instead, it's stored on the cluster's shared NFS volume, which every recipe pod
mounts at ``ELLF_BUILTIN_PATH_NFS``. This means changes are kept when the
service restarts, the image is rebuilt or the package is published again.

Working copies are stored in ``{__nfs__}/marimo/<workspace>/<notebook>.py``.
The user chooses the workspace name when creating the service. Services started
with the same workspace name share the same files, so you can hand a notebook to
a colleague. Services with different workspace names don't share any files.

The first time a notebook is opened in a workspace, it's copied from the
notebook asset. After that, the working copy is never overwritten.
"""

import os
import re
import shutil
from pathlib import Path

#: The environment variable the broker sets on every recipe pod for the shared
#: NFS volume. It's read directly instead of with ``resolve_builtin_path``,
#: because that returns the unresolved ``{__nfs__}/...`` string when running
#: locally, and a local run needs a real directory to write to.
NFS_ENV_VAR = "ELLF_BUILTIN_PATH_NFS"

#: Overrides the workspace root, for local development and tests.
ROOT_ENV_VAR = "ELLF_MARIMO_ROOT"

#: The folder on the NFS volume that this recipe uses.
NFS_SUBDIR = "marimo"

DEFAULT_WORKSPACE = "default"

_NAME_RE = re.compile(r"^[\w-]+$")

# The workspace and notebook names come from a form and are added to a file
# path, so they're validated instead of being rewritten. A rejected name is a
# typo the user can fix, while a rewritten name is a notebook they can't find.
_INVALID_WORKSPACE = (
    "Invalid workspace name {name!r}. Use only letters, numbers, hyphens and "
    "underscores."
)
_INVALID_NOTEBOOK = (
    "Invalid notebook name {name!r}. Use only letters, numbers, hyphens and "
    "underscores, followed by '.py'."
)


def workspace_root() -> Path:
    """Return the directory that holds all workspaces of this recipe."""
    override = os.environ.get(ROOT_ENV_VAR)
    if override:
        return Path(override)
    nfs = os.environ.get(NFS_ENV_VAR)
    if nfs:
        return Path(nfs) / NFS_SUBDIR
    # When running locally, store the files in the current directory, so the
    # notebook can still be edited.
    return Path.cwd() / ".marimo-workspaces"


def validate_workspace(name: str) -> str:
    if not _NAME_RE.match(name):
        raise ValueError(_INVALID_WORKSPACE.format(name=name))
    return name


def validate_notebook(name: str) -> str:
    if not name.endswith(".py") or not _NAME_RE.match(name[: -len(".py")]):
        raise ValueError(_INVALID_NOTEBOOK.format(name=name))
    return name


def resolve_workspace(name: str) -> Path:
    """Return the directory of the workspace ``name``, and create it if needed."""
    directory = workspace_root() / validate_workspace(name)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def seed_notebook(workspace_dir: Path, notebook: str, source: Path) -> Path:
    """Return the path to the working copy of ``notebook`` in the workspace.

    If the working copy doesn't exist yet, it's copied from ``source``, the
    notebook asset's file on shared storage. An existing working copy is never
    overwritten, because it contains the user's changes.

    Args:
        workspace_dir: The workspace directory.
        notebook: The file name of the working copy.
        source: The file to copy the notebook from.

    Returns:
        The path to the working copy, which marimo opens.
    """
    validate_notebook(notebook)
    target = workspace_dir / notebook
    if not target.exists():
        shutil.copyfile(source, target)
    return target
