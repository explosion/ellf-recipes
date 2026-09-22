import marimo

__generated_with = "0.24.2"
app = marimo.App(width="medium", app_title="Dataset Explorer")


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Dataset explorer

    A live view of one annotation dataset, computed on the cluster.

    **This notebook is yours to change.** Every cell below is editable and the
    page recomputes as you edit — change the query, add a column, swap the
    chart. Edits are saved to the notebook file on shared storage, so they
    outlive this service.

    The cells are ordered the way you'd work: *connect → shape → filter →
    look*. The one marked **the query** is the one to reach for first.
    """)
    return


@app.cell
def _():
    import altair as alt
    import marimo as mo
    import pandas as pd

    from ellf_notebook import data

    return alt, data, mo, pd


@app.cell(hide_code=True)
def _(data, mo):
    dataset_name = mo.ui.text(
        value=data.configured_dataset("sample_annotations"),
        label="Dataset",
        full_width=False,
    )
    # Annotation is happening *now*, so offer to re-read on an interval. "off"
    # is the default: a notebook you're editing shouldn't re-run under you.
    auto_refresh = mo.ui.refresh(
        options=["10s", "30s", "2m"], default_interval=None, label="Auto-refresh"
    )
    mo.hstack([dataset_name, auto_refresh], justify="start", gap=2)
    return auto_refresh, dataset_name


@app.cell
def _(auto_refresh, data, dataset_name):
    # Referencing `auto_refresh` is what subscribes this cell to the timer:
    # when it ticks, marimo re-runs this cell and everything downstream.
    auto_refresh

    examples = data.load_examples(dataset_name.value)
    return (examples,)


@app.cell(hide_code=True)
def _(examples, mo):
    mo.callout(
        mo.md(
            f"""
    **Showing bundled sample rows, not your data.**
    {examples.error}

    This happens when the notebook runs off-cluster, or when the dataset can't
    be read. Everything below still works — it just isn't your dataset.
    """
        ),
        kind="warn",
    ) if examples.is_sample else mo.md(
        f"**{len(examples.rows)}** annotations in `{examples.dataset}`."
    )
    return


@app.cell
def _(examples, pd):
    # ─── the query ────────────────────────────────────────────────────────────
    # One row in, one row out: flatten each Prodigy annotation into the columns
    # you want to slice by. This is the cell to edit — add a column from
    # `meta`, pull a score out, count tokens, whatever the question needs.
    #
    # Every annotation is a plain dict. To see what's actually in one:
    #     examples.rows[0]

    def labels_of(eg):
        # Where the labels live depends on the interface: spans for
        # ner/spancat, a single `label` for classification, `accept` for the
        # choice interfaces. Taking all three means this works on whatever
        # dataset you point it at.
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
                f"{accepted / total:.0%}" if total else "—",
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
    # ─── the charts ───────────────────────────────────────────────────────────
    # Plain Altair, wrapped in `mo.ui.altair_chart`. The wrapper is what turns
    # a chart into an *input*: whatever you click or brush becomes
    # `label_chart.value`, a dataframe of just those rows, and the table at the
    # bottom reads it. Change the encodings, swap `mark_bar` for `mark_point`,
    # add a facet — the page re-renders on save.

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
    # Click a bar in the chart above and this table narrows to those
    # annotations; click away to get everything back.
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

    The notebook runs inside a job pod, which is handed a short-lived token for
    the user who started it. The Ellf SDK picks that up on its own, so listing
    what's on the cluster is two lines — and you only ever see what you're
    allowed to see.
    """)
    return


@app.cell
def _(data, mo, pd):
    client = data.pam_client()
    cluster = data.cluster_id()

    if client is None or cluster is None:
        cluster_view = mo.md(
            "_No job credentials in this environment — running off-cluster._"
        )
    else:
        cluster_view = mo.ui.table(
            pd.DataFrame(data.cluster_datasets(client, cluster)), page_size=8
        )
    cluster_view
    return


if __name__ == "__main__":
    app.run()
