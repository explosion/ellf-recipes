"""The notebook asset type.

Registering notebooks as assets means the service form lists the notebooks on
your cluster, instead of a fixed list from the package. To add a notebook, you
register it as an asset, without publishing the package again.

The asset is the source of the notebook. The service copies it into a
workspace the first time it's opened and marimo edits the copy, so people
using different workspaces don't overwrite each other's changes.
"""

from typing import ClassVar, Literal

from ellf_recipes_sdk import Asset, ellf_type


@ellf_type(
    "notebook",
    title="Notebook",
    description=(
        "The notebook to open. Choose a notebook registered on your cluster. "
        "Notebooks you register are also listed here."
    ),
)
class Notebook(Asset[Literal["notebook"]]):
    """A marimo notebook registered on the cluster.

    ``path`` is the ``.py`` file on shared storage. It's copied into a
    workspace and never edited directly.
    """

    # fmt: off
    kind: ClassVar[Literal["notebook"]] = "notebook"  # pyright: ignore[reportIncompatibleVariableOverride]
    # fmt: on

    @property
    def filename(self) -> str:
        """The file name of the working copy in a workspace."""
        return self.path.rsplit("/", 1)[-1]
