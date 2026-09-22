"""Starting marimo, shared by every notebook recipe in this package.

The recipes differ only in what they ask for on the form and which notebook
they open. Everything about *running* marimo is the same, so it lives here and
each recipe is left as a signature plus one call.

This is a port-mode service. The recipe launches marimo's own server and
returns ``None``, and the SDK runner keeps the process alive while the cluster
routes and health-checks marimo's port.
"""

import os
import subprocess
import sys
from typing import Dict, Optional

from .workspace import resolve_workspace, seed_notebook

#: marimo's default port. Non-privileged, so it is honored as-is both on the
#: cluster (the container port the Service targets and probes) and on local
#: runs, where ``resolve_service_port`` only overrides privileged ports.
MARIMO_PORT = 2718


#: Seeded into an otherwise empty workspace so its home page has something to
#: open. A workspace that already holds notebooks is left alone.
FALLBACK_NOTEBOOK = "blank.py"


def launch(
    *,
    workspace: str,
    notebook: Optional[str] = None,
    read_only: bool = False,
    env_extra: Optional[Dict[str, str]] = None,
) -> None:
    """Serve ``workspace`` with marimo, or one notebook inside it.

    Args:
        workspace: Folder name on shared storage to keep notebooks in.
        notebook: Filename to open within the workspace, seeded from the
            bundled starter of the same name on first use and never
            overwritten afterwards. ``None`` opens marimo's own home page
            instead, which lists the workspace and can create new notebooks.
        read_only: Serve as an app (``marimo run``) rather than an editor.
            Requires ``notebook``, since an app is one notebook.
        env_extra: Extra environment for the marimo process, which is how a
            recipe tells its notebook what it was started with.

    Returns:
        ``None``, because the marimo subprocess is the server.

    Raises:
        ValueError: If ``read_only`` is set without a ``notebook``.
    """
    if read_only and notebook is None:
        raise ValueError("read_only needs a notebook, because an app is one notebook")

    workspace_dir = resolve_workspace(workspace)
    if notebook is None:
        notebook_path = None
        # An empty workspace would otherwise open on an empty home page, with
        # nothing to click and no hint of what this is wired up to.
        if not any(workspace_dir.glob("*.py")):
            seed_notebook(workspace_dir, FALLBACK_NOTEBOOK)
    else:
        notebook_path = seed_notebook(workspace_dir, notebook)

    # marimo runs as a fresh process, so config is handed over via env vars
    # rather than function arguments. Everything else in the environment is
    # inherited on purpose: PRODIGY_CONFIG_OVERRIDES (the database connection)
    # and ELLF_PAM_* (the job's credentials) are what make the notebook's first
    # cells work without any setup.
    env = os.environ.copy()
    env["ELLF_MARIMO_WORKSPACE"] = str(workspace_dir)
    env.update(env_extra or {})

    # marimo keeps user settings (theme, keymap, formatting) under the XDG
    # directories and *creates* them on first start. Pointing them into the
    # workspace does two things: it stops the start-up depending on a writable
    # home directory in the pod, and it makes those settings persist with the
    # workspace the same way the notebook does.
    settings_dir = workspace_dir / ".marimo"
    for xdg_var in ("XDG_CONFIG_HOME", "XDG_CACHE_HOME", "XDG_STATE_HOME"):
        env[xdg_var] = str(settings_dir)

    # Bind to the declared service port (what the cluster routes and probes),
    # honoring ELLF_RECIPES_PORT for local overrides -- mirrors the SDK's
    # resolve_service_port contract for app-mode services.
    port = int(os.environ.get("ELLF_RECIPES_PORT", MARIMO_PORT))

    argv = [
        sys.executable,
        "-m",
        "marimo",
        # Answer prompts non-interactively: there is no terminal to answer them.
        "-y",
        "run" if read_only else "edit",
    ]
    # No filename means the home page, which is how the general-purpose recipe
    # lets people pick an existing notebook or start a new one.
    if notebook_path is not None:
        argv.append(str(notebook_path))
    argv += [
        "--headless",
        "--host",
        "0.0.0.0",
        "--port",
        str(port),
        # Auth is the ingress's job; see any recipe's module docstring.
        "--no-token",
    ]
    if read_only:
        # An app whose code you can't read is a strange thing to hand a
        # colleague, and the code is already visible to anyone who can open
        # the editor on the same workspace.
        argv.append("--include-code")
    else:
        # Nothing in a recipe pod can act on "a new marimo is available".
        argv.append("--skip-update-check")

    # cwd is the workspace so marimo's file browser is rooted there, and so a
    # notebook that writes a CSV writes it somewhere that persists.
    subprocess.Popen(argv, cwd=str(workspace_dir), env=env)
    return None
