"""Starting the marimo server for a notebook.

The recipe starts marimo's own server and returns ``None``. The SDK keeps the
process running while the cluster routes requests to marimo's port and checks
its health.
"""

import os
import subprocess
import sys
from pathlib import Path

from .workspace import resolve_workspace, seed_notebook

#: marimo's default port. It's not a privileged port, so it's used as is on the
#: cluster and locally, where ``resolve_service_port`` only overrides
#: privileged ports.
MARIMO_PORT = 2718


def launch(
    *, workspace: str, notebook: str, source: str, read_only: bool = False
) -> None:
    """Serve a notebook from a workspace with marimo.

    Args:
        workspace: The name of the folder on shared storage for the working copy.
        notebook: The file name of the working copy in the workspace.
        source: The notebook asset's path on shared storage. The working copy is
            created from it the first time and never overwritten after that.
        read_only: Serve the notebook as an app with ``marimo run`` instead of
            an editor.

    Returns:
        ``None``, because the marimo process is the server.
    """
    workspace_dir = resolve_workspace(workspace)
    notebook_path = seed_notebook(workspace_dir, notebook, Path(source))

    # The marimo process inherits the whole environment, including
    # PRODIGY_CONFIG_OVERRIDES with the database connection and ELLF_PAM_* with
    # the user's credentials. This is why the notebooks work without any setup.
    env = os.environ.copy()

    # marimo creates its user settings in the XDG directories when it starts.
    # Storing them in the workspace means marimo doesn't need a writable home
    # directory in the pod, and the settings are kept with the notebook.
    settings_dir = workspace_dir / ".marimo"
    for xdg_var in ("XDG_CONFIG_HOME", "XDG_CACHE_HOME", "XDG_STATE_HOME"):
        env[xdg_var] = str(settings_dir)

    # Use the port the service declares, which the cluster routes to and
    # checks. ELLF_RECIPES_PORT overrides it for local runs, like the SDK's
    # resolve_service_port does.
    port = int(os.environ.get("ELLF_RECIPES_PORT", MARIMO_PORT))

    argv = [
        sys.executable,
        "-m",
        "marimo",
        # There's no terminal to answer prompts, so answer yes to all of them.
        "-y",
        "run" if read_only else "edit",
        str(notebook_path),
        "--headless",
        "--host",
        "0.0.0.0",
        "--port",
        str(port),
        # The ingress handles authentication, so marimo's token is turned off.
        "--no-token",
    ]
    if read_only:
        # Show the code in the app. Anyone who can open the editor on the same
        # workspace can already read it.
        argv.append("--include-code")
    else:
        # Nothing in a recipe pod can install a new version of marimo.
        argv.append("--skip-update-check")

    # Run marimo in the workspace, so its file browser starts there and files a
    # notebook writes are stored on shared storage.
    subprocess.Popen(argv, cwd=str(workspace_dir), env=env)
    return None
