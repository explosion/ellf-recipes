"""Action recipe: put this package's notebooks on the cluster as assets.

Publishing a recipe package registers recipes, not assets, so the notebook
picker starts empty. Run this once after publishing and the notebooks that
ship here become assets anyone can select.

It is deliberately a separate step rather than something the service does on
start. Registering assets is a write to the platform, and a service that
quietly creates records the first time somebody opens it is hard to reason
about later, when you are trying to work out where an asset came from.

Nothing here is special. The same two calls register a notebook you wrote
yourself, which is the point of notebooks being assets at all.
"""

import shutil
from pathlib import Path

from ellf_recipes_sdk import action_recipe

from ..types import Notebook
from ..workspace import bundled_notebooks, workspace_root, _templates_dir

#: Where registered notebooks live. Beside the workspaces rather than inside
#: one, because a source is not owned by any workspace that copies it.
STARTERS_DIRNAME = "starters"


@action_recipe(
    title="Register Notebooks",
    description=(
        "Copy the notebooks that ship with this package onto shared storage "
        "and register each one as an asset, so they appear in the notebook "
        "picker when you create a Marimo Notebook service."
    ),
)
def register_notebooks(*, version: str = "0.1.0", overwrite: bool = False) -> None:
    """Register every bundled notebook as a ``notebook`` asset.

    Args:
        version: Version to register the assets under. Asset names are unique
            per name and version, so re-running with the same version fails
            unless the asset was removed.
        overwrite: Replace the file on shared storage if it is already there.
            The asset record is what makes a notebook selectable, and the file
            is what gets copied into workspaces, so refreshing the file
            changes what *new* workspaces start from without touching anyone's
            working copy.

    Returns:
        ``None``. Progress is logged.
    """
    starters = workspace_root() / STARTERS_DIRNAME
    starters.mkdir(parents=True, exist_ok=True)

    for filename in bundled_notebooks():
        target = starters / filename
        if overwrite or not target.exists():
            shutil.copyfile(_templates_dir() / filename, target)
        name = Path(filename).stem
        if Notebook.exists(name):
            print(f"Already registered, skipping: {name}")
            continue
        Notebook.create(
            name=name,
            path=str(target),
            version=version,
            meta={"filename": filename},
        )
        print(f"Registered notebook asset: {name} -> {target}")
    return None
