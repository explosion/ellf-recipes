"""Helpers the notebooks use to read data from Prodigy and Ellf.

This module handles connecting to the Prodigy database and creating an
authenticated Ellf SDK client from the service's credentials. The queries,
aggregations and charts are in the notebooks, where users can edit them.

The imports of ``prodigy`` and the SDK client are inside the functions,
because recipe discovery imports every module of a recipe package. Importing
them at module level would slow down the CLI and every task that loads this
package.

If a dataset can't be read, for example because it doesn't exist in the
database Prodigy connects to, :func:`load_examples` doesn't raise an error.
Instead, it returns no rows and sets :attr:`Examples.error`, so the notebook
can show what went wrong.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class Examples:
    """The annotations in a dataset, or the reason they couldn't be read."""

    rows: List[Dict[str, Any]] = field(default_factory=list)
    dataset: str = ""
    #: Set if the dataset couldn't be read, in which case ``rows`` is empty.
    error: str = ""

    @property
    def failed(self) -> bool:
        return bool(self.error)


def load_examples(name: str) -> Examples:
    """Read all annotations in the dataset ``name`` from the Prodigy database.

    ``get_dataset_examples`` returns the annotations as dictionaries in
    Prodigy's JSON format, which you can use directly in a notebook.
    """
    if not name:
        return Examples(dataset=name, error="No dataset name given.")
    try:
        from prodigy.components.db import connect
    except Exception as exc:  # noqa: BLE001
        return Examples(dataset=name, error=f"Prodigy isn't installed ({exc}).")
    try:
        db = connect()
        rows = db.get_dataset_examples(name)
    except Exception as exc:  # noqa: BLE001
        return Examples(dataset=name, error=f"{type(exc).__name__}: {exc}")
    if rows is None:
        return Examples(
            dataset=name, error=f"Dataset {name!r} doesn't exist in the database."
        )
    return Examples(rows=list(rows), dataset=name)


def pam_client() -> Optional[Any]:
    """Return an authenticated Ellf SDK client, or ``None`` without a job token.

    The service runs with a short-lived token for the user who started it, so
    the client makes requests on behalf of that user and only sees what they
    have access to.

    Returns ``None`` if there's no token or the SDK isn't installed, which is
    the case when you run the notebook locally.
    """
    settings = _sdk_settings()
    if settings is None:
        return None
    from ellf_pam_sdk.client.full_client import Client

    if not settings.pam_host or not settings.job_token:
        return None
    return Client.from_job_token_sync(settings.pam_host, settings.job_token)


def cluster_id() -> Optional[Any]:
    """Return the ID of the cluster the service runs on, if it's known."""
    settings = _sdk_settings()
    return None if settings is None else settings.cluster_id


def _sdk_settings() -> Optional[Any]:
    try:
        from ellf_pam_sdk.recipe_client import Settings
    except Exception:  # noqa: BLE001
        return None
    return Settings()


def cluster_datasets(client: Any, cluster: Any) -> List[Dict[str, Any]]:
    """List the datasets on the cluster, newest first.

    This returns Ellf's record of each dataset, not its contents. To read the
    annotations in a dataset, use :func:`load_examples`.
    """
    from ellf_pam_sdk.models import DatasetReading

    rows = [
        {
            "name": ds.name,
            "kind": ds.kind,
            "created": ds.created,
            "updated": ds.updated,
            "id": str(ds.id),
        }
        for ds in client.dataset.all(DatasetReading(cluster_id=cluster))
    ]
    return sorted(rows, key=lambda row: row["created"], reverse=True)


def _resolve_asset_path(client: Any, cluster: Any, path: str) -> str:
    """Resolve path aliases like ``{__nfs__}`` or ``{models}`` in an asset path.

    Asset paths are stored as they were entered, so they often start with a
    built-in or custom path alias. If the alias can't be resolved, the path is
    returned unchanged, and reading the file then fails with a clear error.
    """
    from ellf_recipes_sdk import resolve_remote_path

    try:
        return resolve_remote_path(client, path, cluster)
    except Exception:  # noqa: BLE001
        return path


def cluster_assets(
    client: Any, cluster: Any, kind: Optional[str] = None
) -> List[Dict[str, Any]]:
    """List the assets on the cluster, optionally only of a given kind.

    An asset is Ellf's record of a file on shared storage, like a trained
    model, a results file, a PDF or a patterns file. Path aliases in each
    ``path`` are resolved, so you can open the file directly.
    """
    from ellf_pam_sdk.models import AssetReading

    query = AssetReading(cluster_id=cluster, kind=kind or None)
    return [
        {
            "name": asset.name,
            "kind": asset.kind,
            "version": asset.version,
            "path": _resolve_asset_path(client, cluster, asset.path),
            "created": asset.created,
            "meta": asset.meta,
            "id": str(asset.id),
        }
        for asset in client.asset.all(query)
    ]


def load_json_asset(path: str) -> Dict[str, Any]:
    """Read a JSON asset from shared storage, using the ``path`` returned by
    :func:`cluster_assets`.

    The ``train`` recipe saves the scores of each run as a JSON file next to
    the model, registered as an asset of kind ``"results"``.
    """
    import json

    return json.loads(Path(path).read_text(encoding="utf8"))


def load_model(target: str) -> Any:
    """Load a trained spaCy pipeline.

    ``target`` is either a path on shared storage or the name of an installed
    package. If the pipeline can't be loaded, this raises an error, because an
    error analysis without the right model would be meaningless.
    """
    import spacy

    return spacy.load(target)


def training_corpora(model_path: str) -> Dict[str, Any]:
    """Return the datasets each component of a pipeline was trained and
    evaluated on.

    spaCy saves the training config in the model directory, and Prodigy's
    corpus readers record the dataset names in it for each trained component.
    The results asset doesn't include them, so this reads the config of the
    model.

    Returns a dictionary with ``datasets`` and ``eval_datasets``, which map
    each trained component like ``"ner"`` to its dataset names, and
    ``eval_split``. If the config can't be read, it returns an empty dictionary.

    If a component was evaluated on named datasets, scoring the pipeline on them
    reproduces the reported scores. If the run held back a share of the training
    data with ``eval_split`` instead, the examples in that split aren't saved.
    """
    cfg_path = Path(model_path) / "config.cfg"
    if not cfg_path.exists():
        return {}
    try:
        from confection import Config

        cfg = Config().from_disk(cfg_path)
    except Exception:  # noqa: BLE001
        return {}

    corpora = cfg.get("corpora") or {}
    blocks = {name: block for name, block in corpora.items() if isinstance(block, dict)}
    return {
        "datasets": {name: block.get("datasets") or [] for name, block in blocks.items()},
        "eval_datasets": {
            name: block.get("eval_datasets") or [] for name, block in blocks.items()
        },
        "eval_split": corpora.get("eval_split"),
    }


def cluster_jobs(client: Any, cluster: Any) -> List[Dict[str, Any]]:
    """List the tasks and actions in Ellf in one table, newest first.

    Tasks start annotation servers that annotators connect to, and actions run
    workflows like training or imports to completion. Actions are filtered by
    cluster. Tasks can't be, because the SDK's task query has no cluster
    filter, so all tasks you have access to are listed.
    """
    from ellf_pam_sdk.models import ActionReading, TaskReading

    rows: List[Dict[str, Any]] = []
    for job in client.task.all(TaskReading()):
        rows.append(
            {
                "name": job.name,
                "job_type": str(job.job_type),
                "recipe": job.recipe_name,
                "project": job.project_name,
                "created": job.created,
                "id": str(job.id),
            }
        )
    for job in client.action.all(ActionReading(cluster_id=cluster)):
        rows.append(
            {
                "name": job.name,
                "job_type": str(job.job_type),
                "recipe": "",
                "project": "",
                "created": job.created,
                "id": str(job.id),
            }
        )
    return sorted(rows, key=lambda row: row["created"], reverse=True)
