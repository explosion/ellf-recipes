"""Service recipe: a marimo notebook, running on the cluster, editable in the browser.

This is a *port-mode* service recipe. Instead of returning an ASGI app for the
SDK to serve under uvicorn, it launches marimo's own server and returns
``None``; the SDK runner then just keeps the process alive while the cluster
routes and health-checks marimo's port. The Streamlit dashboard in
``ellf_recipes`` works the same way -- see
``ellf_recipes/recipes/services/annotation_dashboard/recipe.py``.

Three things make it work behind the platform's ingress:

* **Routing.** The public route is ``/services/{job_id}/`` and Traefik strips
  that prefix before the request reaches the pod, so marimo is served at its own
  root with no ``--base-url``. marimo's HTML references assets relatively
  (``./assets/...``) and its frontend derives every API and websocket URL from
  ``document.baseURI``, so the prefix survives the round trip. The trailing
  slash on the public route is what makes that resolution correct, and the
  platform's ingress path already carries one.
* **Auth.** ``auth="session"`` gates the route at the ingress: a logged-in
  project member gets in from the web app, everyone else does not. marimo's own
  token auth is therefore turned off (``--no-token``) rather than layered on
  top, where it would just be a second password prompt on an already
  authenticated route.
* **Persistence.** The notebook file lives on the shared NFS volume, not in the
  image -- see ``workspace.py``. Edits made in the browser are edits to that
  file.

Note what that adds up to: anyone who can open this service can execute
arbitrary Python inside the cluster, as the user who started the job. That is
what a notebook *is*, and it's why the recipe defaults to ``auth="session"``
(project members only) and offers ``read_only`` for handing the result to a
wider audience.

Avoid ``from __future__ import annotations`` here -- the recipe schema builder
reads parameter annotations live via ``inspect.signature`` and expects the
actual classes (``InputDataset``), not strings.
"""

import os
import subprocess
import sys

from ellf_recipes_sdk import BoolProps, InputDataset, TextProps, service_recipe

from ..workspace import (
    DEFAULT_NOTEBOOK,
    DEFAULT_WORKSPACE,
    bundled_notebooks,
    resolve_workspace,
    seed_notebook,
)

# marimo's default port; non-privileged, so it is honored as-is both on the
# cluster (the container port the Service targets and probes) and on local runs
# (resolve_service_port only overrides privileged ports).
MARIMO_PORT = 2718


@service_recipe(
    title="Marimo Notebook",
    description=(
        "An editable marimo notebook running on your cluster, wired up to "
        "Prodigy and the Ellf SDK. Query a dataset, change the code, and the "
        "charts recompute as you type. Notebooks are saved to shared storage, "
        "so edits outlive the service."
    ),
    port=MARIMO_PORT,
    healthcheck_path="/health",
    auth="session",
    field_props={
        "workspace": TextProps(
            title="Workspace",
            description=(
                "Folder on shared storage holding this notebook and anything "
                "it writes. Reuse a workspace name to pick up where you (or a "
                "colleague) left off; pick a new one for a clean slate."
            ),
            placeholder=DEFAULT_WORKSPACE,
        ),
        "notebook": TextProps(
            title="Notebook file",
            description=(
                "Which .py file in the workspace to open. A file that doesn't "
                "exist yet is created from the matching starter notebook, or "
                "from a blank one if the name isn't a starter. Starters "
                "shipped with this package: "
                + ", ".join(bundled_notebooks())
                + "."
            ),
            placeholder=DEFAULT_NOTEBOOK,
        ),
        "read_only": BoolProps(
            title="Share as a read-only app",
            description=(
                "Serve the notebook as an app instead of an editor: viewers "
                "can use the filters and read the code, but not change it. "
                "Use this to hand a finished analysis to a wider audience."
            ),
        ),
    },
)
def marimo_notebook(
    *,
    dataset: InputDataset,
    workspace: str = DEFAULT_WORKSPACE,
    notebook: str = DEFAULT_NOTEBOOK,
    read_only: bool = False,
) -> None:
    """Launch marimo over a notebook on shared storage and keep it running.

    Args:
        dataset: The dataset the starter notebook opens with. It is a starting
            point, not a binding -- the notebook can read any dataset on the
            cluster, and the dataset name is an editable field on the page.
        workspace: Name of the folder on shared storage to keep notebooks in.
        notebook: Filename of the notebook to open within the workspace.
        read_only: Serve as a read-only app (``marimo run``) rather than an
            editor (``marimo edit``).

    Returns:
        ``None`` -- this is a port-mode service: the marimo subprocess is the
        server, and the SDK just keeps the process alive.
    """
    workspace_dir = resolve_workspace(workspace)
    notebook_path = seed_notebook(workspace_dir, notebook)

    # marimo runs as a fresh process, so config is handed over via env vars
    # rather than function arguments. Everything else in the environment is
    # inherited on purpose: PRODIGY_CONFIG_OVERRIDES (the database connection)
    # and ELLF_PAM_* (the job's credentials) are what make the notebook's first
    # two cells work without any setup.
    env = os.environ.copy()
    env["ELLF_MARIMO_DATASET"] = dataset.name
    env["ELLF_MARIMO_WORKSPACE"] = str(workspace_dir)

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
        str(notebook_path),
        "--headless",
        "--host",
        "0.0.0.0",
        "--port",
        str(port),
        # Auth is the ingress's job; see the module docstring.
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
