"""Service recipe: explore one annotation dataset in a marimo notebook.

A named service rather than a generic notebook launcher, so it shows up in the
Services list as the thing it is and asks only for what it needs. The notebook
it opens is editable in the browser and lives on shared storage, so the code
people write here outlives the service.

Avoid ``from __future__ import annotations`` here -- the recipe schema builder
reads parameter annotations live via ``inspect.signature`` and expects the
actual classes (``InputDataset``), not strings.
"""

from ellf_recipes_sdk import BoolProps, InputDataset, TextProps, service_recipe

from ..launcher import MARIMO_PORT, launch
from ..workspace import DEFAULT_WORKSPACE

NOTEBOOK = "dataset_explorer.py"


@service_recipe(
    title="Dataset Explorer",
    description=(
        "A live view of one annotation dataset, computed on your cluster. "
        "Label distribution, throughput by annotator, and a browsable table, "
        "all in a notebook you can edit in the browser. Change the query and "
        "the charts recompute as you type."
    ),
    port=MARIMO_PORT,
    healthcheck_path="/health",
    auth="session",
    category="dashboard",
    field_props={
        "workspace": TextProps(
            title="Workspace",
            description=(
                "Folder on shared storage holding this notebook and anything "
                "it writes. Reuse a workspace name to pick up where you (or a "
                "colleague) left off, or pick a new one for a clean slate."
            ),
            placeholder=DEFAULT_WORKSPACE,
        ),
        "read_only": BoolProps(
            title="Share as a read-only app",
            description=(
                "Serve the notebook as an app instead of an editor, so "
                "viewers can use the filters and read the code but not change "
                "it. Use this to hand a finished analysis to a wider audience."
            ),
        ),
    },
)
def dataset_explorer(
    *,
    dataset: InputDataset,
    workspace: str = DEFAULT_WORKSPACE,
    read_only: bool = False,
) -> None:
    """Open the dataset explorer notebook on ``dataset``.

    Args:
        dataset: The dataset the notebook opens with. A starting point rather
            than a binding, since the notebook can read any dataset on the
            cluster and the name is an editable field on the page.
        workspace: Name of the folder on shared storage to keep notebooks in.
        read_only: Serve as a read-only app rather than an editor.

    Returns:
        ``None``, because this is a port-mode service.
    """
    return launch(
        notebook=NOTEBOOK,
        workspace=workspace,
        read_only=read_only,
        env_extra={"ELLF_MARIMO_DATASET": dataset.name},
    )
