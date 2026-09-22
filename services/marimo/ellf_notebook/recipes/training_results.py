"""Service recipe: what a training run scored, and what it gets wrong.

Takes the trained pipeline as a form field rather than making the notebook
hunt for one. The ``train`` recipe registers two assets per run, the pipeline
itself as ``kind="model"`` and a JSON payload of metrics beside it as
``kind="results"``, named ``<model>.results``. Picking the model is enough to
find both.

Declaring the model as a recipe input also matters for packaged pipelines.
When an asset's ``meta["format"]`` is ``"package"`` its wheel is pip-installed
into the container before Python starts, which only happens for models the
recipe actually declares.

Avoid ``from __future__ import annotations`` here -- the recipe schema builder
reads parameter annotations live via ``inspect.signature`` and expects the
actual classes (``Model``, ``InputDataset``), not strings.
"""

from ellf_recipes_sdk import BoolProps, InputDataset, Model, TextProps, service_recipe

from ..launcher import MARIMO_PORT, launch
from ..workspace import DEFAULT_WORKSPACE

NOTEBOOK = "training_results.py"


@service_recipe(
    title="Training Results",
    description=(
        "Scores from a training run, and the examples the model gets wrong. "
        "Per-label F-scores from the run's metrics, then the pipeline scored "
        "against a dataset so you can see its false positives and false "
        "negatives. Click a label to filter down to its mistakes."
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
def training_results(
    *,
    model: Model,
    dataset: InputDataset,
    workspace: str = DEFAULT_WORKSPACE,
    read_only: bool = False,
) -> None:
    """Open the training-results notebook on ``model``.

    Args:
        model: The trained pipeline to report on. Its metrics come from the
            matching ``kind="results"`` asset, and the pipeline itself is what
            the error analysis runs.
        dataset: Annotations to score the model against. Only accepted
            examples count as gold.
        workspace: Name of the folder on shared storage to keep notebooks in.
        read_only: Serve as a read-only app rather than an editor.

    Returns:
        ``None``, because this is a port-mode service.
    """
    return launch(
        notebook=NOTEBOOK,
        workspace=workspace,
        read_only=read_only,
        env_extra={
            "ELLF_MARIMO_DATASET": dataset.name,
            "ELLF_MARIMO_MODEL": model.name,
            # A packaged pipeline is pip-installed into the container before
            # Python starts, so it loads by its spaCy name. A directory one
            # loads by path. Resolving that here keeps the notebook to a plain
            # spacy.load of whatever it is handed.
            "ELLF_MARIMO_MODEL_TARGET": (
                str(model.meta.get("spacy_model_name", model.name))
                if model.meta.get("format") == "package"
                else model.path
            ),
        },
    )
