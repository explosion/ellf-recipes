import marimo

__generated_with = "0.24.2"
app = marimo.App(width="medium", app_title="Training results")


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Training results

    What a training run scored, and below that, *which examples it gets wrong*.

    Pick a training run below. Its metrics come from the `kind="results"`
    asset the `train` recipe writes beside every pipeline, and the pipeline
    itself is what the error analysis runs.

    The charts are clickable. Selecting a bar filters the tables underneath,
    which is the point of doing this in a notebook rather than a dashboard.
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
    # The service runs notebooks, it does not know what any one of them wants,
    # so the choice of training run lives here. The train recipe registers
    # metrics as `<model>.results`, so listing those assets lists the runs.
    runs = (
        data.cluster_assets(client, cluster, kind="results")
        if client is not None
        else []
    )
    run_picker = mo.ui.dropdown(
        options={f"{a['name']}  ({a['version']})": a for a in runs},
        value=(
            f"{runs[0]['name']}  ({runs[0]['version']})" if runs else None
        ),
        label="Training run",
    )
    run_picker if runs else mo.callout(
        mo.md("""
    **No training runs on this cluster yet.**

    The `train` recipe registers a `kind="results"` asset when a run finishes
    with saving enabled. A run with *Skip saving outputs* ticked leaves
    nothing to report on.
    """),
        kind="warn",
    )
    return (run_picker,)


@app.cell
def _(data, run_picker):
    results = (
        data.load_json_asset(run_picker.value["path"]) if run_picker.value else {}
    )
    performance = results.get("performance") or {}
    model_name = (
        run_picker.value["name"].removesuffix(".results") if run_picker.value else ""
    )
    return model_name, performance, results


@app.cell(hide_code=True)
def _(mo, model_name, performance):
    mo.md(f"Reporting on **{model_name}**.") if performance else mo.md("")
    return


@app.cell(hide_code=True)
def _(mo, performance):
    def _headline(key, label):
        value = performance.get(key)
        return mo.stat(
            f"{value:.3f}" if isinstance(value, (int, float)) else "—",
            label=label,
            bordered=True,
        )

    mo.hstack(
        [
            _headline("ents_f", "NER F"),
            _headline("ents_p", "Precision"),
            _headline("ents_r", "Recall"),
            _headline("cats_macro_f", "Textcat macro F"),
        ],
        widths="equal",
        gap=1,
    ) if performance else mo.md("")
    return


@app.cell
def _(pd, performance):
    # ─── per-label scores ─────────────────────────────────────────────────────
    # `ents_per_type` is where spaCy puts the per-label breakdown. Swap the key
    # for `cats_f_per_type` if you trained a text classifier.
    per_type = performance.get("ents_per_type") or {}
    scores = pd.DataFrame(
        [
            {"label": label, "p": s.get("p"), "r": s.get("r"), "f": s.get("f")}
            for label, s in per_type.items()
        ]
    )
    scores.sort_values("f") if not scores.empty else scores
    return (scores,)


@app.cell(hide_code=True)
def _(alt, mo, scores):
    score_chart = (
        mo.ui.altair_chart(
            alt.Chart(scores)
            .mark_bar(cornerRadiusEnd=3)
            .encode(
                x=alt.X("f:Q", title="F-score", scale=alt.Scale(domain=[0, 1])),
                y=alt.Y("label:N", title=None, sort="x"),
                tooltip=["label:N", "p:Q", "r:Q", "f:Q"],
            )
            .properties(height=220, title="F-score by label, click a bar")
        )
        if not scores.empty
        else None
    )
    score_chart if score_chart is not None else mo.md("_No per-label scores._")
    return (score_chart,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Error analysis

    Scores tell you *that* something is wrong. This tells you *what*.

    The pipeline is run over the annotations in a dataset and each predicted
    entity is compared against the gold spans on the same text.

    * **false positive**, predicted but not annotated
    * **false negative**, annotated but not predicted

    Only accepted annotations count as gold. Rejected and skipped ones are
    excluded.
    """)
    return


@app.cell(hide_code=True)
def _(data, mo):
    dataset_name = mo.ui.text(
        value=data.configured_dataset(),
        label="Evaluate against dataset",
        full_width=False,
    )
    sample_size = mo.ui.slider(
        start=25, stop=1000, step=25, value=200, label="Examples to score"
    )
    run_analysis = mo.ui.run_button(label="Run error analysis")
    mo.hstack([dataset_name, sample_size, run_analysis], justify="start", gap=2)
    return dataset_name, run_analysis, sample_size


@app.cell
def _(client, cluster, data, dataset_name, model_name, run_analysis, sample_size):
    # Loading a pipeline and running it over hundreds of texts is the one slow
    # thing here, so it sits behind a button rather than re-running every time
    # a filter changes.
    errors = []
    analysis_note = ""

    if run_analysis.value and model_name:
        models = [
            a
            for a in (
                data.cluster_assets(client, cluster, kind="model")
                if client is not None
                else []
            )
            if a["name"] == model_name
        ]
        if not models:
            analysis_note = f"No model asset named `{model_name}` on this cluster."
        else:
            asset = models[0]
            target = (
                asset["meta"].get("spacy_model_name", model_name)
                if asset["meta"].get("format") == "package"
                else asset["path"]
            )
            examples = data.load_examples(dataset_name.value)
            gold_rows = [
                eg for eg in examples.rows if eg.get("answer") == "accept"
            ][: sample_size.value]
            if not gold_rows:
                analysis_note = (
                    f"No accepted annotations in `{dataset_name.value}`."
                )
            else:
                nlp = data.load_model(target)
                for eg in gold_rows:
                    text = eg.get("text", "")
                    gold = {
                        (s["start"], s["end"], s["label"])
                        for s in (eg.get("spans") or [])
                        if "label" in s
                    }
                    pred = {
                        (ent.start_char, ent.end_char, ent.label_)
                        for ent in nlp(text).ents
                    }
                    for start, end, label in pred - gold:
                        errors.append(
                            {
                                "kind": "false positive",
                                "label": label,
                                "span": text[start:end],
                                "text": text,
                            }
                        )
                    for start, end, label in gold - pred:
                        errors.append(
                            {
                                "kind": "false negative",
                                "label": label,
                                "span": text[start:end],
                                "text": text,
                            }
                        )
                analysis_note = (
                    f"Scored **{len(gold_rows)}** accepted annotations from "
                    f"`{examples.dataset}` with **{model_name}**."
                )
    else:
        analysis_note = "Press **Run error analysis** to score the model."
    return analysis_note, errors


@app.cell(hide_code=True)
def _(analysis_note, mo):
    mo.md(analysis_note) if analysis_note else mo.md("")
    return


@app.cell
def _(errors, pd):
    error_df = pd.DataFrame(errors)
    error_df
    return (error_df,)


@app.cell(hide_code=True)
def _(alt, error_df, mo):
    # Wrapping the chart in `mo.ui.altair_chart` is what makes it an *input*.
    # `error_chart.value` is the rows behind whatever you click, and the table
    # in the next cell reads it.
    error_chart = (
        mo.ui.altair_chart(
            alt.Chart(error_df)
            .mark_bar(cornerRadiusEnd=3)
            .encode(
                x=alt.X("count()", title="Errors"),
                y=alt.Y("label:N", title=None, sort="-x"),
                color=alt.Color("kind:N", title=None),
                tooltip=["label:N", "kind:N", "count()"],
            )
            .properties(height=240, title="Errors by label, click to filter")
        )
        if not error_df.empty
        else None
    )
    error_chart if error_chart is not None else mo.md(
        "_No errors to chart yet._"
    )
    return (error_chart,)


@app.cell(hide_code=True)
def _(error_chart, error_df, mo):
    selected = (
        error_chart.value
        if error_chart is not None and not error_chart.value.empty
        else error_df
    )
    mo.ui.table(selected, page_size=10) if not selected.empty else mo.md(
        "_Nothing selected._"
    )
    return


@app.cell(hide_code=True)
def _(mo, score_chart):
    # The score chart is an input too. This reads back whichever labels you
    # clicked up top, which is handy when comparing worst F against most
    # errors, because they are not always the same labels.
    mo.md(
        f"Selected in the score chart: `{list(score_chart.value['label'])}`"
    ) if score_chart is not None and not score_chart.value.empty else mo.md("")
    return


if __name__ == "__main__":
    app.run()
