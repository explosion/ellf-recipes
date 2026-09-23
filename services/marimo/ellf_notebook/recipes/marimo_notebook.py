"""Service recipe that runs a marimo notebook on your cluster.

The service asks which notebook to open and where to keep the working copy. If
a notebook needs anything else, like a dataset to read or a model to score, it
asks for it on the page, using the Ellf SDK. This way, each notebook can offer
exactly the inputs it needs, and you can change them without publishing the
package again.

Notebooks are registered as assets, so the form lists the notebooks on your
cluster. When you register your own notebook, it's listed there too.

Don't use ``from __future__ import annotations`` in this module. The recipe
schema builder reads the parameter annotations with ``inspect.signature`` and
expects the actual classes, like ``Notebook``, not strings.
"""

import os
import subprocess
import sys
from pathlib import Path

from ellf_recipes_sdk import BoolProps, TextProps, service_recipe

from ..types import Notebook
from ..workspace import DEFAULT_WORKSPACE, resolve_workspace, seed_notebook

#: marimo's default port. The cluster routes requests to it and checks its
#: health.
MARIMO_PORT = 2718


@service_recipe(
    title="Marimo Notebook",
    # Recipe descriptions are limited to 255 characters. A longer description
    # isn't rejected before it's saved, so publishing fails with a 500 error.
    description=(
        "Run a marimo notebook on your cluster, next to the Prodigy database "
        "and behind Ellf's authentication. Edit the notebook in your browser "
        "and see the results update as you type. Changes are saved to shared "
        "storage."
    ),
    port=MARIMO_PORT,
    healthcheck_path="/health",
    auth="session",
    category="dashboard",
    field_props={
        "workspace": TextProps(
            title="Workspace",
            description=(
                "Folder on shared storage for the working copy and any files "
                "the notebook writes. To continue where you or a colleague "
                "left off, use the same name. To start from the notebook as it "
                "was registered, use a new name."
            ),
            placeholder=DEFAULT_WORKSPACE,
        ),
        "read_only": BoolProps(
            title="Share as a read-only app",
            description=(
                "Serve the notebook as an app instead of an editor, so "
                "viewers can use its controls and read the code but not "
                "change it. Use this to share a finished analysis."
            ),
        ),
    },
)
def marimo_notebook(
    *,
    notebook: Notebook,
    workspace: str = DEFAULT_WORKSPACE,
    read_only: bool = False,
) -> None:
    """Open ``notebook`` in ``workspace`` with marimo's own server.

    marimo isn't an ASGI app, so the recipe starts its server and returns
    ``None``. The SDK then keeps the recipe running while the cluster routes
    requests to marimo's port.

    Args:
        notebook: The notebook to run. Its file is copied into the workspace
            the first time, so changes don't affect anyone using the same
            notebook in another workspace.
        workspace: The name of the folder on shared storage for the working
            copy.
        read_only: Serve the notebook as an app instead of an editor.

    Returns:
        ``None``, because the recipe runs its own server.
    """
    workspace_dir = resolve_workspace(workspace)
    notebook_path = seed_notebook(
        workspace_dir, notebook.filename, Path(notebook.path)
    )

    # The marimo process inherits the service's environment, which includes the
    # Prodigy database connection and the user's credentials. This is why the
    # notebooks work without any setup.
    env = os.environ.copy()
    # marimo creates its user settings when it starts. Storing them in the
    # workspace means marimo doesn't need a writable home directory, and the
    # settings are kept with the notebook.
    for xdg_var in ("XDG_CONFIG_HOME", "XDG_CACHE_HOME", "XDG_STATE_HOME"):
        env[xdg_var] = str(workspace_dir / ".marimo")

    # ELLF_RECIPES_PORT overrides the port for local runs.
    port = os.environ.get("ELLF_RECIPES_PORT", str(MARIMO_PORT))
    argv = [
        sys.executable, "-m", "marimo",
        # There's no terminal to answer prompts, so answer yes to all of them.
        "-y",
        "run" if read_only else "edit",
        str(notebook_path),
        "--headless", "--host", "0.0.0.0", "--port", port,
        # Ellf handles authentication, so marimo's own token is turned off.
        "--no-token",
    ]
    if read_only:
        # Show the code in the app. Anyone who can open the editor on the same
        # workspace can already read it.
        argv.append("--include-code")
    else:
        # A recipe pod can't install a new version of marimo.
        argv.append("--skip-update-check")

    # Run marimo in the workspace, so its file browser starts there and files a
    # notebook writes are stored on shared storage.
    subprocess.Popen(argv, cwd=str(workspace_dir), env=env)
    return None
