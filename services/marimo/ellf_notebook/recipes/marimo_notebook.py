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

from ellf_recipes_sdk import BoolProps, TextProps, service_recipe

from ..launcher import MARIMO_PORT, launch
from ..types import Notebook
from ..workspace import DEFAULT_WORKSPACE


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
    """Open ``notebook`` in ``workspace`` and keep marimo running.

    Args:
        notebook: The notebook to run. Its file is copied into the workspace
            the first time, so changes don't affect anyone using the same
            notebook in another workspace.
        workspace: The name of the folder on shared storage for the working
            copy.
        read_only: Serve the notebook as an app instead of an editor.

    Returns:
        ``None``, because this is a port-mode service.
    """
    return launch(
        notebook=notebook.filename,
        source=notebook.path,
        workspace=workspace,
        read_only=read_only,
    )
