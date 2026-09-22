"""Where the editable notebooks live, and how they get there.

A marimo notebook *is* a Python file, and the whole point of this service is
that people edit it. So the file cannot live inside the container image: that
copy is read-only in spirit and thrown away when the pod restarts. It lives on
the cluster's shared NFS volume instead, which every recipe pod mounts
read-write at ``ELLF_BUILTIN_PATH_NFS`` -- so an edit made in the browser
survives a restart, an image rebuild, and a republish of this package.

The layout is::

    {__nfs__}/marimo/<workspace>/<notebook>.py

``<workspace>`` is a name the user picks when creating the service. Two
services started with the same workspace name share the same files (deliberate
-- that is how you hand a notebook to a colleague); two different names are
fully isolated.

Starter notebooks ship inside the package under ``notebooks/``. They are copied
into the workspace once, on first start, and never again: after that the file on
NFS is the source of truth and the bundled copy is only a template for the next
new notebook.
"""

import os
import re
import shutil
from pathlib import Path
from typing import List

#: Env var the broker sets on every recipe pod for the shared NFS mount. See
#: ``ellf_recipes_sdk.sdk.paths._BUILTIN_PATH_ENV_VARS`` for the full map -- we
#: read it directly rather than through ``resolve_builtin_path`` because that
#: helper hands back the unresolved ``{__nfs__}/...`` string off-cluster, and
#: here the off-cluster case needs a real local directory to write into.
NFS_ENV_VAR = "ELLF_BUILTIN_PATH_NFS"

#: Escape hatch for local development (`ELLF_MARIMO_ROOT=/tmp/nb`) and for the
#: tests, which must not touch a real mount.
ROOT_ENV_VAR = "ELLF_MARIMO_ROOT"

#: Subdirectory of the NFS mount this recipe owns.
NFS_SUBDIR = "marimo"

DEFAULT_WORKSPACE = "default"

_NAME_RE = re.compile(r"^[\w-]+$")

# The workspace name and notebook filename both reach us from a form field and
# are joined onto a filesystem path, so they are validated rather than
# sanitised: a rejected name is a fixable typo, a silently rewritten one is a
# notebook the user cannot find again.
_INVALID_WORKSPACE = (
    "Invalid workspace name {name!r}: use letters, numbers, dashes and "
    "underscores only."
)
_INVALID_NOTEBOOK = (
    "Invalid notebook name {name!r}: use letters, numbers, dashes and "
    "underscores, ending in '.py'."
)


def workspace_root() -> Path:
    """Root directory holding every workspace of this recipe."""
    override = os.environ.get(ROOT_ENV_VAR)
    if override:
        return Path(override)
    nfs = os.environ.get(NFS_ENV_VAR)
    if nfs:
        return Path(nfs) / NFS_SUBDIR
    # Off-cluster (a local `ptr run`, a test): keep the files next to the
    # process instead of failing, so the notebook is still editable.
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
    """Return the workspace directory for ``name``, creating it if needed."""
    directory = workspace_root() / validate_workspace(name)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def bundled_notebooks() -> List[str]:
    """Filenames of the starter notebooks shipped inside this package."""
    return sorted(p.name for p in _templates_dir().glob("*.py"))


def _templates_dir() -> Path:
    return Path(__file__).parent / "notebooks"


def seed_notebook(workspace_dir: Path, notebook: str) -> Path:
    """Return the path to ``notebook`` in the workspace, seeding it if absent.

    An existing file is never overwritten -- it holds the user's edits. A
    missing one is copied from the bundled starter of the same name, or, for a
    name we don't ship, created from the blank starter so that ``marimo edit``
    opens something valid rather than an empty file.
    """
    validate_notebook(notebook)
    target = workspace_dir / notebook
    if target.exists():
        return target
    template = _templates_dir() / notebook
    if not template.exists():
        template = _templates_dir() / "blank.py"
    shutil.copyfile(template, target)
    return target
