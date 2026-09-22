"""The notebook asset type.

A notebook is a plain ``.py`` file, so making it an asset costs nothing and
buys a lot. The service-creation form gets a real picker listing the notebooks
that exist on the cluster, rather than a dropdown frozen into the package at
publish time, and anyone can add to that list by registering an asset without
republishing anything.

An asset is the *source*. The service copies it into a workspace on first use
and marimo edits the copy, so two people opening the same notebook do not
write over each other. That split is the same one the package used to have
between bundled starters and workspace copies, with the platform supplying the
sources instead of the wheel.
"""

from typing import ClassVar, Literal

from ellf_recipes_sdk import Asset, ellf_type


@ellf_type(
    "notebook",
    title="Notebook",
    description=(
        "Which notebook to open. Pick one registered on your cluster, or "
        "register your own and it shows up here."
    ),
)
class Notebook(Asset[Literal["notebook"]]):
    """A marimo notebook registered on the cluster.

    ``path`` points at the ``.py`` file on shared storage. The file is the
    source that gets copied into a workspace, never the thing edited in the
    browser.
    """

    # fmt: off
    kind: ClassVar[Literal["notebook"]] = "notebook"  # pyright: ignore[reportIncompatibleVariableOverride]
    # fmt: on

    @property
    def filename(self) -> str:
        """Name the working copy takes inside a workspace."""
        return self.path.rsplit("/", 1)[-1]
