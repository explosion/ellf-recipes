import marimo

__generated_with = "0.24.2"
app = marimo.App(width="medium", app_title="Ellf objects")


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # A new notebook

    Everything below already works — it is a reference for reaching the three
    kinds of Ellf object from inside a notebook. Delete what you don't need and
    keep writing.

    The pod you're running in was handed a short-lived token for whoever
    started this service, so every call here is made *as that user* and sees
    exactly what they're allowed to see. There is nothing to configure.
    """)
    return


@app.cell
def _():
    import marimo as mo
    import pandas as pd

    from ellf_notebook import data

    client = data.pam_client()
    cluster = data.cluster_id()
    return client, cluster, data, mo, pd


@app.cell(hide_code=True)
def _(client, cluster, mo):
    mo.callout(
        mo.md("""
    **No job credentials in this environment.**
    The platform sections below will be empty. Reading a dataset still works if
    a Prodigy database is reachable; otherwise you get the bundled sample rows.
    """),
        kind="warn",
    ) if client is None or cluster is None else mo.md(
        f"Connected to cluster `{cluster}`."
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 1. Datasets

    A dataset is *annotations*, and they live in the cluster's Prodigy
    database. `load_examples` hands you plain dicts — no typed-example API to
    learn first.
    """)
    return


@app.cell
def _(data):
    examples = data.load_examples(data.configured_dataset())

    # examples.rows    -> list[dict], one per annotation
    # examples.source  -> "prodigy" when real, "sample" when falling back
    # examples.dataset -> the name that was read
    examples.rows[:1]
    return (examples,)


@app.cell
def _(client, cluster, data, mo, pd):
    # The *platform's* record of what datasets exist, which is a different
    # question from what is inside one.
    mo.ui.table(pd.DataFrame(data.cluster_datasets(client, cluster)), page_size=5) \
        if client is not None else mo.md("_No client._")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 2. Assets

    An asset is the platform's record of a *file* on shared storage: a trained
    model, a results JSON, a PDF, a patterns file. The `path` you get back is
    already a concrete mount this pod can read, so there is no download step
    and no alias to resolve.
    """)
    return


@app.cell
def _(client, cluster, data, mo, pd):
    assets = data.cluster_assets(client, cluster) if client is not None else []

    # Filter by kind when you know what you're after:
    #   data.cluster_assets(client, cluster, kind="model")
    #   data.cluster_assets(client, cluster, kind="results")
    mo.ui.table(pd.DataFrame(assets), page_size=5) if assets else mo.md(
        "_No assets on this cluster yet._"
    )
    return (assets,)


@app.cell
def _(assets, mo):
    from pathlib import Path

    # An asset's contents are a plain file read. This previews the first one;
    # `data.load_json_asset(path)` is the shortcut for JSON, and
    # `data.load_model(path)` loads a spaCy pipeline from a kind="model" asset.
    preview = (
        Path(assets[0]["path"]).read_text(encoding="utf8")[:400]
        if assets and Path(assets[0]["path"]).exists()
        else ""
    )
    mo.md(f"```\n{preview}\n```") if preview else mo.md("_Nothing to preview._")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 3. Jobs

    Tasks (annotation servers people open) and actions (batch jobs that run to
    completion) listed together — usually what you want when the question is
    "what has been run on this cluster".
    """)
    return


@app.cell
def _(client, cluster, data, mo, pd):
    jobs = data.cluster_jobs(client, cluster) if client is not None else []
    mo.ui.table(pd.DataFrame(jobs), page_size=5) if jobs else mo.md(
        "_No tasks or actions on this cluster yet._"
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Going further

    `client` is the full Ellf SDK client, so anything the platform exposes is
    reachable — `client.project`, `client.recipe`, `client.package`,
    `client.secret` and the rest all follow the same
    `client.<thing>.all(<Thing>Reading(cluster_id=cluster))` shape.

    For worked examples, open `dataset_explorer.py` (annotations) or
    `training_results.py` (model scores and error analysis) in this same
    workspace.
    """)
    return


if __name__ == "__main__":
    app.run()
