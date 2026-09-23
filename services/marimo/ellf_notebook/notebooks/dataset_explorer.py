import marimo

__generated_with = "0.24.2"
app = marimo.App(width="medium", app_title="Dataset Explorer")


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Dataset explorer

    This notebook shows the annotations in a dataset on your cluster, with
    statistics, charts and a table you can filter.

    You can **edit any cell**, for example to change the query, add a column or
    change a chart. When you run a cell, all cells that depend on it update.
    Your changes are saved to the notebook file on shared storage, so they're
    kept after the service stops.

    The cells load the dataset, convert the annotations to a table, filter
    them and then visualize the results. To change which information is
    extracted from each annotation, start with the cell marked **the query**.
    """)
    return


@app.cell
def _():
    import altair as alt
    import marimo as mo
    import pandas as pd

    from ellf_notebook import data

    client = data.pam_client()
    cluster = data.cluster_id()
    return alt, client, cluster, data, mo, pd


@app.cell(hide_code=True)
def _(client, cluster, data, mo):
    # The service doesn't pass in a dataset, so you choose one here. The
    # dropdown lists the datasets on your cluster that the user who started
    # the service has access to. If there's no list, for example because the
    # notebook runs locally without a job token, you can type a name instead.
    # The dataset is then read from the Prodigy database configured on your
    # machine.
    names = sorted(
        d["name"] for d in data.cluster_datasets(client, cluster)
    ) if client is not None and cluster is not None else []
    dataset_name = (
        mo.ui.dropdown(
            options=names,
            value=names[0] if names else None,
            label="Dataset",
        )
        if names
        else mo.ui.text(
            value="",
            label="Dataset",
            full_width=False,
        )
    )
    # To see new annotations as they come in, you can re-read the dataset on
    # an interval. It's off by default, so the notebook doesn't re-run while
    # you're editing it.
    auto_refresh = mo.ui.refresh(
        options=["10s", "30s", "2m"], default_interval=None, label="Auto-refresh"
    )
    mo.hstack([dataset_name, auto_refresh], justify="start", gap=2)
    return auto_refresh, dataset_name


@app.cell
def _(auto_refresh, data, dataset_name, mo):
    # Referencing `auto_refresh` makes this cell depend on the timer, so marimo
    # re-runs this cell and all cells that depend on it on every interval.
    auto_refresh

    # Wait for a dataset name before reading anything.
    mo.stop(
        not dataset_name.value,
        mo.md("_Enter the name of a dataset to explore its annotations._"),
    )
    examples = data.load_examples(dataset_name.value)

    # If the dataset can't be read, `mo.stop` shows the error and the cells
    # below don't run.
    mo.stop(
        examples.failed,
        mo.callout(
            mo.md(f"""
    **Couldn't read annotations from the Prodigy database.**

    `{examples.error}`

    To troubleshoot this, check the following.

    - **The notebook is running on your cluster.** If you're running it
      locally, Prodigy uses your local database, which is SQLite in
      `~/.prodigy` by default, so the datasets on your cluster aren't
      available. Start the notebook as a service on your cluster instead.
    - **The dataset exists.** Choose a dataset from the list above, or run
      `ellf datasets list`.
    - **The database is reachable.** If you see a connection or authentication
      error, restart the service. If the error persists, run
      `ellf clusters check` to check the health of your cluster.
    """),
            kind="danger",
        ),
    )
    return (examples,)


@app.cell(hide_code=True)
def _(examples, mo):
    mo.md(f"**{len(examples.rows)}** annotations in `{examples.dataset}`.")
    return


@app.cell
def _(examples, pd):
    # The query
    #
    # This cell converts each annotation into one row of a table, with the
    # columns you want to filter and group by. Edit `to_record` to add your own
    # columns, for example a value from `meta`, a score or a token count.
    #
    # Each annotation is a dictionary in Prodigy's JSON format. To inspect one,
    # run `examples.rows[0]` in a new cell.

    def labels_of(eg):
        # Where the labels are stored depends on the annotation interface. The
        # ner and spancat interfaces use `spans`, classification uses `label`
        # and choice uses `accept`. Reading all three lets this work with any
        # dataset.
        labels = {span["label"] for span in (eg.get("spans") or []) if "label" in span}
        if eg.get("label"):
            labels.add(eg["label"])
        labels.update(c for c in (eg.get("accept") or []) if isinstance(c, str))
        return sorted(labels)

    def to_record(eg):
        return {
            "text": eg.get("text", ""),
            "answer": eg.get("answer", "ignore"),
            "annotator": (eg.get("_annotator_id") or eg.get("_session_id") or "unknown"),
            "n_spans": len(eg.get("spans") or []),
            "labels": labels_of(eg),
            "channel": (eg.get("meta") or {}).get("channel", ""),
            "timestamp": eg.get("_timestamp"),
        }

    df = pd.DataFrame([to_record(eg) for eg in examples.rows])
    if not df.empty:
        df["annotated_at"] = pd.to_datetime(df["timestamp"], unit="s", utc=True)
    df
    return (df,)


@app.cell(hide_code=True)
def _(df, mo):
    all_labels = sorted({label for labels in df["labels"] for label in labels}) if not df.empty else []
    all_annotators = sorted(df["annotator"].unique()) if not df.empty else []

    label_filter = mo.ui.multiselect(
        options=all_labels, value=all_labels, label="Labels"
    )
    annotator_filter = mo.ui.multiselect(
        options=all_annotators, value=all_annotators, label="Annotators"
    )
    decision_filter = mo.ui.multiselect(
        options=["accept", "reject", "ignore"],
        value=["accept", "reject", "ignore"],
        label="Decisions",
    )
    mo.hstack(
        [label_filter, annotator_filter, decision_filter], justify="start", gap=2
    )
    return annotator_filter, decision_filter, label_filter


@app.cell
def _(annotator_filter, decision_filter, df, label_filter):
    selected_labels = set(label_filter.value)
    keep = (
        df["annotator"].isin(annotator_filter.value)
        & df["answer"].isin(decision_filter.value)
        & df["labels"].apply(lambda labels: bool(selected_labels.intersection(labels)) or not labels)
    ) if not df.empty else df
    view = df[keep] if not df.empty else df
    return (view,)


@app.cell(hide_code=True)
def _(mo, view):
    accepted = int((view["answer"] == "accept").sum()) if not view.empty else 0
    total = len(view)
    mo.hstack(
        [
            mo.stat(total, label="Annotations", bordered=True),
            mo.stat(accepted, label="Accepted", bordered=True),
            mo.stat(
                f"{accepted / total:.0%}" if total else "N/A",
                label="Accept rate",
                bordered=True,
            ),
            mo.stat(
                int(view["n_spans"].sum()) if not view.empty else 0,
                label="Spans",
                bordered=True,
            ),
        ],
        widths="equal",
        gap=1,
    )
    return


@app.cell
def _(alt, mo, pd, view):
    # The charts
    #
    # The charts use Altair. Wrapping a chart in `mo.ui.altair_chart` lets you
    # select data in it. The rows you click or brush are available as
    # `label_chart.value`, which the table at the bottom uses. You can change
    # the encodings, mark type or facets, and the page updates when you save.

    label_counts = (
        pd.DataFrame(
            [
                {"label": label, "answer": answer}
                for labels, answer in zip(view["labels"], view["answer"])
                for label in labels
            ]
        )
        if not view.empty
        else pd.DataFrame(columns=["label", "answer"])
    )

    label_chart = (
        alt.Chart(label_counts)
        .mark_bar(cornerRadiusEnd=3)
        .encode(
            x=alt.X("count()", title="Annotations"),
            y=alt.Y("label:N", title=None, sort="-x"),
            color=alt.Color("answer:N", title="Decision"),
            tooltip=["label:N", "answer:N", "count()"],
        )
        .properties(height=220, title="Annotations per label")
    )

    over_time = (
        alt.Chart(view.reset_index())
        .mark_line(point=True)
        .encode(
            x=alt.X("yearmonthdatehours(annotated_at):T", title="Annotated"),
            y=alt.Y("count()", title="Annotations"),
            color=alt.Color("annotator:N", title="Annotator"),
            tooltip=["annotator:N", "count()"],
        )
        .properties(height=220, title="Throughput by annotator")
        if not view.empty
        else alt.Chart(pd.DataFrame({"x": []})).mark_point()
    )

    label_chart = mo.ui.altair_chart(label_chart)
    mo.vstack([label_chart, over_time])
    return (label_chart,)


@app.cell(hide_code=True)
def _(label_chart, mo, view):
    # Click a bar in the chart above to only show those annotations in this
    # table. Click outside the bars to show all annotations again.
    picked = label_chart.value
    rows = (
        view[view["labels"].apply(lambda ls: bool(set(picked["label"]) & set(ls)))]
        if not picked.empty
        else view
    )
    mo.ui.table(rows.drop(columns=["timestamp"], errors="ignore"), page_size=8)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## The rest of the cluster

    The service runs with a short-lived token for the user who started it, and
    the Ellf SDK uses this token automatically. This means you can list what's
    on your cluster without configuring any credentials, and you only see what
    that user has access to.
    """)
    return


@app.cell
def _(client, cluster, data, mo, pd):
    if client is None or cluster is None:
        cluster_view = mo.md(
            "_No job credentials found. The notebook is running locally._"
        )
    else:
        cluster_view = mo.ui.table(
            pd.DataFrame(data.cluster_datasets(client, cluster)), page_size=8
        )
    cluster_view
    return


if __name__ == "__main__":
    app.run()
