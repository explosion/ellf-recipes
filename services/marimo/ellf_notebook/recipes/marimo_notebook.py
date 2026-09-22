"""Service recipe: a marimo workspace on your cluster.

The general case. ``dataset_explorer`` and ``training_results`` are named
services that open one analysis and ask for what it needs. This one opens the
*workspace* and lets marimo's own home page take it from there, listing the
notebooks that are actually in the folder and offering to create a new one.

That is deliberately not a form field. A dropdown built at publish time cannot
see a notebook a colleague wrote last week, and a text box means knowing the
filename before you start. The directory knows, so the directory decides.

There is no read-only option here for the same reason. ``marimo run`` serves
one notebook as an app, so it needs a filename. Handing over a finished
analysis is what the named recipes are for.

Avoid ``from __future__ import annotations`` here -- the recipe schema builder
reads parameter annotations live via ``inspect.signature`` and expects the
actual classes (``InputDataset``), not strings.
"""

from ellf_recipes_sdk import InputDataset, TextProps, service_recipe

from ..launcher import MARIMO_PORT, launch
from ..workspace import DEFAULT_WORKSPACE


@service_recipe(
    title="Marimo Notebook",
    description=(
        "A marimo workspace on your cluster, wired up to Prodigy and the Ellf "
        "SDK. Opens on a list of the notebooks in the workspace, where you "
        "can pick one or start a new one. Notebooks are saved to shared "
        "storage, so edits outlive the service."
    ),
    port=MARIMO_PORT,
    healthcheck_path="/health",
    auth="session",
    category="dashboard",
    field_props={
        "workspace": TextProps(
            title="Workspace",
            description=(
                "Folder on shared storage holding these notebooks and "
                "anything they write. Reuse a workspace name to pick up where "
                "you (or a colleague) left off, or pick a new one for a clean "
                "slate. A new workspace starts with one notebook showing how "
                "to reach datasets, assets and jobs."
            ),
            placeholder=DEFAULT_WORKSPACE,
        ),
    },
)
def marimo_notebook(
    *,
    dataset: InputDataset,
    workspace: str = DEFAULT_WORKSPACE,
) -> None:
    """Open ``workspace`` in marimo and keep it running.

    Args:
        dataset: The dataset the notebooks open with. A starting point rather
            than a binding, since a notebook can read any dataset on the
            cluster.
        workspace: Name of the folder on shared storage to keep notebooks in.

    Returns:
        ``None``, because this is a port-mode service.
    """
    return launch(
        workspace=workspace,
        env_extra={"ELLF_MARIMO_DATASET": dataset.name},
    )
