"""Service recipe: run a marimo notebook on your cluster.

A notebook runner, and deliberately nothing more. It asks which notebook and
where to keep the working copy, and that is all. What a notebook needs in
order to do its job, a dataset to read or a model to score, it asks for
itself, from inside the page, using the Ellf SDK it is already authenticated
against.

Putting those on this form instead would mean one set of arguments for every
notebook anyone ever writes, which fits none of them. A notebook that wants a
dataset and a date range and two thresholds can offer exactly that, as marimo
widgets, and change its mind without republishing anything.

The notebook itself is an asset, so the form lists what is actually on the
cluster rather than what happened to ship in this package. Registering your
own notebook makes it appear in the picker.

Avoid ``from __future__ import annotations`` here -- the recipe schema builder
reads parameter annotations live via ``inspect.signature`` and expects the
actual classes (``Notebook``), not strings.
"""

from ellf_recipes_sdk import BoolProps, TextProps, service_recipe

from ..launcher import MARIMO_PORT, launch
from ..types import Notebook
from ..workspace import DEFAULT_WORKSPACE


@service_recipe(
    title="Marimo Notebook",
    description=(
        "Run a marimo notebook on your cluster, next to the annotation "
        "database and behind your platform's auth. Pick a notebook and it "
        "opens in the browser, editable, with the code and the charts "
        "recomputing as you type. Notebooks are saved to shared storage, so "
        "edits outlive the service."
    ),
    port=MARIMO_PORT,
    healthcheck_path="/health",
    auth="session",
    category="dashboard",
    field_props={
        "workspace": TextProps(
            title="Workspace",
            description=(
                "Folder on shared storage holding the working copy and "
                "anything it writes. Reuse a workspace name to pick up where "
                "you (or a colleague) left off, or pick a new one to start "
                "from the notebook as it was registered."
            ),
            placeholder=DEFAULT_WORKSPACE,
        ),
        "read_only": BoolProps(
            title="Share as a read-only app",
            description=(
                "Serve the notebook as an app instead of an editor, so "
                "viewers can use its controls and read the code but not "
                "change it. Use this to hand a finished analysis to a wider "
                "audience."
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
    """Open ``notebook`` in ``workspace`` and keep marimo running.

    Args:
        notebook: The notebook to run. Its file is the source, copied into the
            workspace on first use so that editing it here cannot disturb
            anybody else running the same notebook elsewhere.
        workspace: Name of the folder on shared storage to keep the working
            copy in.
        read_only: Serve as a read-only app rather than an editor.

    Returns:
        ``None``, because this is a port-mode service.
    """
    return launch(
        notebook=notebook.filename,
        source=notebook.path,
        workspace=workspace,
        read_only=read_only,
        env_extra={"ELLF_MARIMO_NOTEBOOK": notebook.name},
    )
