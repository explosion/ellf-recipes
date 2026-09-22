"""Data plumbing the notebooks import: Prodigy on one side, the cluster on the other.

This module is deliberately thin, and deliberately *not* where the interesting
code lives. The split is the point of the demo:

* **Here** (shipped in the package, stable): how to reach the Prodigy database
  that the annotation tasks write to, and how to get an authenticated Ellf SDK
  client out of the job's own credentials. Plumbing nobody wants to retype.
* **In the notebook** (on NFS, editable in the browser): the query, the
  aggregation, the charts. The part a user should be changing.

Every import of ``prodigy`` and of the SDK client happens *inside* a function.
Recipe discovery imports every module of a recipe package -- in the CLI, in task
pods, wherever -- and a heavyweight import at module scope would fire in all of
them for no reason.

Off-cluster there is no Prodigy database and no job token. Rather than raising,
:func:`load_examples` falls back to the sample rows bundled in ``data/`` and
says so in :attr:`Examples.source`, so the notebook opens and renders while
you're developing it on a laptop. The notebook shows a loud banner whenever the
rows are the sample ones -- a demo that quietly invents data is worse than one
that fails.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

#: Set by the recipe on the marimo process: the dataset the service was
#: created for. The notebook uses it as the initial value of an editable text
#: box, not as a hard binding -- reading a second dataset is one keystroke.
DATASET_ENV_VAR = "ELLF_MARIMO_DATASET"

SOURCE_PRODIGY = "prodigy"
SOURCE_SAMPLE = "sample"

SAMPLE_PATH = Path(__file__).parent / "data" / "sample_annotations.jsonl"


@dataclass
class Examples:
    """Annotation rows plus where they actually came from."""

    rows: List[Dict[str, Any]] = field(default_factory=list)
    #: ``"prodigy"`` for real rows, ``"sample"`` for the bundled fallback.
    source: str = SOURCE_SAMPLE
    dataset: str = ""
    #: Populated when the real read failed; the reason the fallback kicked in.
    error: str = ""

    @property
    def is_sample(self) -> bool:
        return self.source == SOURCE_SAMPLE


def configured_dataset(default: str = "") -> str:
    """Name of the dataset this service was started with."""
    return os.environ.get(DATASET_ENV_VAR, default)


def load_examples(name: str) -> Examples:
    """Read every annotation in dataset ``name`` from the Prodigy database.

    ``get_dataset_examples`` dispatches to the structured or unstructured
    table for us and returns plain dicts, which is what a notebook wants: no
    typed-example API to learn before you can write your first ``len(...)``.
    """
    if not name:
        return _sample(name, "No dataset name given.")
    try:
        from prodigy.components.db import connect
    except Exception as exc:  # noqa: BLE001 - off-cluster, no Prodigy install
        return _sample(name, f"Prodigy is not importable here ({exc}).")
    try:
        db = connect()
        rows = db.get_dataset_examples(name)
    except Exception as exc:  # noqa: BLE001 - surface it, don't kill the page
        return _sample(name, f"{type(exc).__name__}: {exc}")
    if rows is None:
        return _sample(name, f"Dataset {name!r} does not exist on this cluster.")
    return Examples(rows=list(rows), source=SOURCE_PRODIGY, dataset=name)


def load_sample() -> Examples:
    """The bundled sample rows, loaded explicitly."""
    return _sample("sample_annotations", "")


def _sample(dataset: str, error: str) -> Examples:
    import json

    rows = []
    with SAMPLE_PATH.open("r", encoding="utf8") as file_:
        for line in file_:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return Examples(rows=rows, source=SOURCE_SAMPLE, dataset=dataset, error=error)


def pam_client() -> Optional[Any]:
    """An authenticated Ellf SDK client, or ``None`` when there's no job token.

    Every recipe pod is handed a short-lived bootstrap token for the user who
    started the job (``ELLF_PAM_BOOTSTRAP_TOKEN``); exchanging it for an access
    token is what ``from_job_token_sync`` does. So the notebook talks to the
    platform *as the user*, and sees exactly what they're allowed to see.

    ``None`` means "not running as a job" -- no token in the environment, or no
    SDK installed at all, which is the normal state on a laptop.
    """
    settings = _sdk_settings()
    if settings is None:
        return None
    from ellf_pam_sdk.client.full_client import Client

    if not settings.pam_host or not settings.job_token:
        return None
    return Client.from_job_token_sync(settings.pam_host, settings.job_token)


def cluster_id() -> Optional[Any]:
    """UUID of the cluster this job runs on, if known."""
    settings = _sdk_settings()
    return None if settings is None else settings.cluster_id


def _sdk_settings() -> Optional[Any]:
    try:
        from ellf_pam_sdk.recipe_client import Settings
    except Exception:  # noqa: BLE001 - off-cluster, no SDK installed
        return None
    return Settings()


def cluster_datasets(client: Any, cluster: Any) -> List[Dict[str, Any]]:
    """Every dataset registered on the cluster, newest first.

    A platform-level view: this is the Ellf record of the dataset, not its
    contents. Pair it with :func:`load_examples` to go from "what exists" to
    "what's in it".
    """
    from ellf_pam_sdk.models import DatasetReading

    query = DatasetReading(cluster_id=cluster)
    return [
        {
            "name": ds.name,
            "kind": ds.kind,
            "created": ds.created,
            "updated": ds.updated,
            "id": str(ds.id),
        }
        for ds in client.dataset.all(query)
    ]


#: Placeholders the platform stores in asset paths, and the env vars the
#: broker sets on every recipe pod to resolve them. The broker expands these
#: for objects passed *into* a recipe, but an asset fetched at runtime through
#: the SDK comes back with the raw stored string, so this module resolves them
#: itself. Mirrors ``ellf_recipes_sdk.sdk.paths._BUILTIN_PATH_ENV_VARS``.
BUILTIN_PATHS = {
    "__nfs__": "ELLF_BUILTIN_PATH_NFS",
    "__bucket__": "ELLF_BUILTIN_PATH_BUCKET",
    "__data__": "ELLF_BUILTIN_PATH_DATA",
    "__tmp__": "ELLF_BUILTIN_PATH_TMP",
}


def resolve_path(path: str) -> str:
    """Expand a ``{__nfs__}/...`` style alias into a path this pod can open.

    Returns the string unchanged when it holds no placeholder, or when the
    matching env var is missing, which is what happens off-cluster. Callers
    get a path that either works or fails loudly, rather than a silent empty
    read.
    """
    for alias, env_var in BUILTIN_PATHS.items():
        token = "{" + alias + "}"
        if token in path:
            root = os.environ.get(env_var)
            if root:
                path = path.replace(token, root.rstrip("/"))
    return path


def cluster_assets(
    client: Any, cluster: Any, kind: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Every asset registered on the cluster, optionally filtered by kind.

    An asset is the platform's record of a file on shared storage, a trained
    model, a results JSON, a PDF, a patterns file. ``path`` is resolved here
    so it can be opened directly, because what the platform stores is
    whatever the person who registered it typed, often an alias.
    """
    from ellf_pam_sdk.models import AssetReading

    query = AssetReading(cluster_id=cluster, kind=kind or None)
    return [
        {
            "name": asset.name,
            "kind": asset.kind,
            "version": asset.version,
            "path": resolve_path(asset.path),
            "created": asset.created,
            "meta": asset.meta,
            "id": str(asset.id),
        }
        for asset in client.asset.all(query)
    ]


def load_json_asset(path: str) -> Dict[str, Any]:
    """Read a JSON asset off shared storage by the ``path`` on its record.

    Used for ``kind="results"`` assets, which the ``train`` recipe writes as a
    JSON payload next to the model (``<model path>.results.json``).
    """
    import json

    return json.loads(Path(resolve_path(path)).read_text(encoding="utf8"))


#: Set by the training-results recipe: what to hand ``spacy.load``. A
#: directory asset resolves to its path on shared storage, a packaged one to
#: the spaCy name of the wheel the broker installed before Python started.
MODEL_TARGET_ENV_VAR = "ELLF_MARIMO_MODEL_TARGET"

#: Set by the training-results recipe: the name of the model asset, which is
#: also how its metrics are found, as ``<name>.results``.
MODEL_ENV_VAR = "ELLF_MARIMO_MODEL"


def configured_model(default: str = "") -> str:
    """Name of the model asset this service was started with."""
    return os.environ.get(MODEL_ENV_VAR, default)


def configured_model_target(default: str = "") -> str:
    """What to pass to :func:`load_model` for the configured model."""
    return os.environ.get(MODEL_TARGET_ENV_VAR, default)


def load_model(target: str) -> Any:
    """Load a trained spaCy pipeline.

    ``target`` is whatever the recipe resolved, either a path on shared
    storage or an installed package name, so this stays a plain
    ``spacy.load``. It raises rather than falling back, because a silently
    absent model would make an error analysis quietly meaningless.
    """
    import spacy

    return spacy.load(resolve_path(target))


def cluster_jobs(client: Any, cluster: Any) -> List[Dict[str, Any]]:
    """Tasks and actions on the cluster, as one table.

    Two different platform objects with a shared shape: a *task* is an
    annotation server people open, an *action* is a batch job that runs to
    completion (training, imports). Listing them together is usually what you
    want when the question is "what has been run here".
    """
    from ellf_pam_sdk.models import ActionReading, TaskReading

    rows: List[Dict[str, Any]] = []
    for job in client.task.all(TaskReading(cluster_id=cluster)):
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
