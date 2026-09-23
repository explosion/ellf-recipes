import marimo

__generated_with = "0.24.2"
app = marimo.App(width="medium", app_title="Ellf objects")


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # A new notebook

    This notebook shows how to access **datasets, assets and jobs** on your
    cluster from Python. Each section below is a working example you can keep,
    edit or delete.

    The service runs with a short-lived token for the user who started it, so
    every request in this notebook is made on behalf of that user and can only
    see what they have access to. You don't need to configure any credentials.
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
    **No job credentials found in this environment.**
    The sections that list datasets, assets and jobs will be empty. You can
    still read a dataset if a Prodigy database is reachable.
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

    Datasets are named collections of data and annotations in Prodigy's JSON
    format, stored in the database on your cluster. `data.load_examples` reads
    all examples in a dataset and returns them as a list of dictionaries.
    """)
    return


@app.cell
def _(client, cluster, data, mo, pd):
    # Ellf's record of the datasets on your cluster, newest first. This lists
    # the datasets, not their contents.
    datasets = data.cluster_datasets(client, cluster) if client is not None else []
    mo.ui.table(pd.DataFrame(datasets), page_size=5) if datasets else mo.md(
        "_No datasets on this cluster yet._"
    )
    return (datasets,)


@app.cell
def _(data, datasets, mo):
    # Change this to the name of the dataset you want to read. By default, it's
    # the newest dataset on your cluster.
    dataset_name = datasets[0]["name"] if datasets else ""
    examples = data.load_examples(dataset_name)

    # `examples.rows` is a list of dictionaries, one per annotation, and
    # `examples.dataset` is the name of the dataset that was read. If the
    # dataset can't be read, `examples.failed` is True, `examples.rows` is
    # empty and `examples.error` explains why.
    if not dataset_name:
        dataset_view = mo.md(
            "_Set `dataset_name` in this cell to read the annotations in a dataset._"
        )
    elif examples.failed:
        dataset_view = mo.callout(
            mo.md(f"""
    **Couldn't connect to the Prodigy database.**

    `{examples.error or "Unknown error."}`

    To troubleshoot this, check the following.

    - **The notebook is running on your cluster.** If you're running it
      locally, there's no cluster database to connect to. Start it as a service
      on your cluster, or set `PRODIGY_CONFIG_OVERRIDES` or a `prodigy.json` to
      point Prodigy to a database you can reach.
    - **The dataset exists.** Compare the name to the datasets listed above, or
      run `ellf datasets list`.
    - **The database is reachable.** If you see a connection or authentication
      error, restart the service. If the error persists, run
      `ellf clusters check` to check the health of your cluster.
    """),
            kind="danger",
        )
    else:
        dataset_view = examples.rows[:1]
    dataset_view
    return (examples,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 2. Assets

    Assets are pointers to data resources registered with Ellf, like input
    files, patterns, PDFs and trained models. `data.cluster_assets` returns
    each asset with its `path` resolved to a location on shared storage, so
    you can open the file directly from this notebook.
    """)
    return


@app.cell
def _(client, cluster, data, mo, pd):
    assets = data.cluster_assets(client, cluster) if client is not None else []

    # To only list assets of a given kind, pass it as `kind`, for example
    # `data.cluster_assets(client, cluster, kind="model")`.
    mo.ui.table(pd.DataFrame(assets), page_size=5) if assets else mo.md(
        "_No assets on this cluster yet._"
    )
    return (assets,)


@app.cell
def _(assets, mo):
    from pathlib import Path

    # You can read an asset like any other file. This previews the first one.
    # For JSON assets, use `data.load_json_asset(path)`, and for kind="model"
    # assets, use `data.load_model(path)` to load the spaCy pipeline.
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

    Tasks start annotation servers that annotators connect to, and actions run
    workflows like training to completion. `data.cluster_jobs` lists both in
    one table, newest first, so you can see what has been run. Actions are
    limited to your cluster, and tasks include all tasks you have access to.
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

    `client` is the full Ellf SDK client, so you can use it to access anything
    else in Ellf, like projects, recipes, packages and secrets. For example,
    `client.package.all(PackageReading(cluster_id=cluster))` lists the
    packages on your cluster, and `PackageReading` is imported from
    `ellf_pam_sdk.models`.

    For more complete examples, start a service with the `dataset_explorer`
    notebook to explore the annotations in a dataset, or with the
    `training_results` notebook to view model scores and analyze errors.
    """)
    return


if __name__ == "__main__":
    app.run()
