import marimo

__generated_with = "0.24.2"
app = marimo.App(width="medium", app_title="Training results")


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Training results

    This notebook shows the scores of a training run and the examples the
    trained pipeline gets wrong.

    Choose a training run below. The scores are read from the `kind="results"`
    asset that the `train` recipe saves with each pipeline, and the error
    analysis runs the pipeline itself over the annotations in a dataset.

    You can click the bars in the charts to filter the tables below them.
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
    # The service doesn't pass in a training run, so you choose one here. The
    # `train` recipe saves the scores of each run as a `<model>.results` asset,
    # so this lists all assets of kind "results".
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
    **No training runs found on your cluster.**

    The `train` recipe creates a `kind="results"` asset when a run finishes
    and its outputs are saved. If **Skip saving outputs** was selected, the
    run doesn't create any assets to show here.
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
            f"{value:.3f}" if isinstance(value, (int, float)) else "N/A",
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
    # Scores per label
    #
    # spaCy stores the scores per label under `ents_per_type`. If you trained
    # a text classifier, use `cats_f_per_type` instead.
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
            .properties(height=220, title="F-score by label (click to filter)")
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

    The scores show how well the pipeline performs, and the error analysis
    shows the examples it gets wrong. It runs the pipeline over **the
    evaluation set the scores above came from** and compares the predicted
    entities to the annotated spans in the same text, so the mistakes below
    are the mistakes behind those numbers.

    The dataset is read from the training config inside the model, not chosen
    here. Scoring against anything else would give errors that do not
    correspond to the scores.

    - A **false positive** is an entity that was predicted but not annotated.
    - A **false negative** is an entity that was annotated but not predicted.

    Only accepted annotations are used for the comparison. Rejected and
    ignored annotations are excluded.
    """)
    return


@app.cell
def _(client, cluster, data, model_name):
    # Which pipeline this run produced, and what it was evaluated on. spaCy
    # writes the training config into the model directory and the Prodigy
    # readers record the dataset names there, so the provenance comes from the
    # model asset. The results asset does not carry it.
    model_assets = [
        a
        for a in (
            data.cluster_assets(client, cluster, kind="model")
            if client is not None
            else []
        )
        if a["name"] == model_name
    ]
    corpora = data.training_corpora(model_assets[0]["path"]) if model_assets else {}
    eval_datasets = corpora.get("eval_datasets") or []
    return corpora, eval_datasets, model_assets


@app.cell(hide_code=True)
def _(corpora, eval_datasets, mo, model_assets, model_name):
    if not model_assets:
        analysis_ready = False
        analysis_block = mo.callout(
            mo.md(f"""
    **No model asset named `{model_name}` on this cluster.**

    The scores came from a run whose pipeline is no longer registered, so
    there is nothing to score.
    """),
            kind="warn",
        )
    elif not eval_datasets:
        analysis_ready = False
        analysis_block = mo.callout(
            mo.md(f"""
    **This run has no evaluation set to analyze.**

    It held out {corpora.get("eval_split")} of its training data instead of
    using a named dataset. That split is seeded, so training would make the
    same one again, but which examples it chose was never recorded and
    rebuilding it here would mean copying Prodigy's internals and assuming the
    datasets have not changed since.

    Scoring the training data instead would flatter the model and produce
    errors that do not match the scores, so this notebook doesn't offer it.
    Train with a dedicated evaluation dataset to get error analysis on a
    future run.
    """),
            kind="warn",
        )
    else:
        analysis_ready = True
        joined = ", ".join(f"`{d}`" for d in eval_datasets)
        analysis_block = mo.md(f"Evaluation set: {joined}")
    analysis_block
    return (analysis_ready,)


@app.cell(hide_code=True)
def _(analysis_ready, mo):
    sample_size = mo.ui.slider(
        start=25, stop=1000, step=25, value=200, label="Examples to score"
    )
    run_analysis = mo.ui.run_button(label="Run error analysis")
    mo.hstack([sample_size, run_analysis], justify="start", gap=2) \
        if analysis_ready else mo.md("")
    return run_analysis, sample_size


@app.cell
def _(analysis_ready, data, eval_datasets, model_assets, run_analysis, sample_size):
    # Loading the pipeline and running it over hundreds of texts can take a
    # while, so it only runs when you click the button, not every time a
    # filter changes.
    errors = []
    analysis_note = ""

    if run_analysis.value and analysis_ready:
        asset = model_assets[0]
        target = (
            asset["meta"].get("spacy_model_name", asset["name"])
            if asset["meta"].get("format") == "package"
            else asset["path"]
        )
        # The evaluation set may be more than one dataset, so read them all
        # and score the union, which is what the metrics were computed over.
        gold_rows = []
        read_errors = []
        for name in eval_datasets:
            examples = data.load_examples(name)
            if examples.failed:
                read_errors.append(f"`{name}` ({examples.error})")
            gold_rows.extend(
                eg for eg in examples.rows if eg.get("answer") == "accept"
            )
        gold_rows = gold_rows[: sample_size.value]
        if read_errors:
            analysis_note = (
                "Couldn't read the evaluation set from the Prodigy database. "
                "Failed to read " + ", ".join(read_errors) + "."
            )
        elif not gold_rows:
            empty_from = ", ".join(f"`{d}`" for d in eval_datasets)
            analysis_note = f"No accepted annotations in {empty_from}."
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
            scored_from = ", ".join(f"`{d}`" for d in eval_datasets)
            analysis_note = (
                f"Scored **{len(gold_rows)}** accepted annotations from "
                f"the evaluation set, {scored_from}."
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
    # Wrapping the chart in `mo.ui.altair_chart` lets you select data in it.
    # The rows you click are available as `error_chart.value`, which the
    # table in the next cell uses.
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
            .properties(height=240, title="Errors by label (click to filter)")
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
    # You can also select labels in the score chart above. This shows which
    # labels are selected, so you can compare the labels with the lowest
    # F-score to the labels with the most errors. These aren't always the same.
    picked_labels = (
        list(score_chart.value["label"])
        if score_chart is not None and not score_chart.value.empty
        else []
    )
    mo.md(
        "You selected "
        + ", ".join(f"`{label}`" for label in picked_labels)
        + " in the score chart."
    ) if picked_labels else mo.md("")
    return


if __name__ == "__main__":
    app.run()
