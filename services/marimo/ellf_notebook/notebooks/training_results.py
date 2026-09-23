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

    The error analysis only works for runs that meet both of these
    requirements.

    - **The run trained a named entity recognizer.** The analysis compares the
      entities the pipeline predicts to the annotated spans. To analyze other
      components, like a text classifier, edit the error analysis cell to
      compare their predictions to the annotations instead.
    - **The run was evaluated on a separate evaluation dataset.** The analysis
      needs the exact examples behind the scores. If the run held back part
      of the training data for evaluation instead, or the evaluation data was
      a file, those examples aren't available.

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
    # The `train` recipe registers the model as `<name>` and its scores as
    # `<name>.results`, with the same version.
    model_name = (
        run_picker.value["name"].removesuffix(".results") if run_picker.value else ""
    )
    model_version = run_picker.value["version"] if run_picker.value else ""
    return model_name, model_version, performance, results


@app.cell(hide_code=True)
def _(mo, model_name, model_version, performance):
    mo.md(
        f"Reporting on **{model_name}** version {model_version}."
    ) if performance else mo.md("")
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
    evaluation dataset the scores above are based on** and compares the
    predicted entities to the annotated spans in the same text. This means the
    errors below are the errors behind those scores.

    The evaluation dataset is read from the training config saved with the
    model, so you can't choose a different one here. Errors from another
    dataset wouldn't match the scores.

    - A **false positive** is an entity that was predicted but not annotated.
    - A **false negative** is an entity that was annotated but not predicted.

    Only accepted annotations are used for the comparison. Rejected and
    ignored annotations are excluded.
    """)
    return


@app.cell
def _(client, cluster, data, model_name, model_version):
    # Find the model asset of this run and the datasets it was evaluated on.
    # spaCy saves the training config in the model directory, and Prodigy's
    # corpus readers record the dataset names in it. The results asset doesn't
    # include them, so they're read from the model. The version has to match
    # too, because the same model name can be trained more than once. The
    # error analysis compares entities, so it only uses the evaluation
    # datasets of the named entity recognizer.
    model_assets = [
        a
        for a in (
            data.cluster_assets(client, cluster, kind="model")
            if client is not None
            else []
        )
        if a["name"] == model_name and a["version"] == model_version
    ]
    corpora = data.training_corpora(model_assets[0]["path"]) if model_assets else {}
    eval_datasets = (corpora.get("eval_datasets") or {}).get("ner") or []
    return corpora, eval_datasets, model_assets


@app.cell(hide_code=True)
def _(corpora, eval_datasets, mo, model_assets, model_name, model_version):
    if not model_assets:
        analysis_ready = False
        analysis_block = mo.callout(
            mo.md(f"""
    **No model asset named `{model_name}` with version {model_version} on this
    cluster.**

    The pipeline of this run isn't registered anymore, so there's no model to
    run the error analysis with.
    """),
            kind="warn",
        )
    elif not corpora:
        analysis_ready = False
        analysis_block = mo.callout(
            mo.md(f"""
    **Couldn't read the training config of `{model_name}`.**

    The error analysis reads the evaluation datasets from the `config.cfg` in
    the model directory. This model doesn't have a readable config, for example
    because it was registered as a package instead of a directory.
    """),
            kind="warn",
        )
    elif "ner" not in corpora.get("datasets", {}):
        analysis_ready = False
        analysis_block = mo.callout(
            mo.md("""
    **This run didn't train a named entity recognizer.**

    The error analysis compares predicted entities to annotated spans. To
    analyze other components, edit the error analysis cell below.
    """),
            kind="warn",
        )
    elif any(d.startswith("__train_") for d in eval_datasets):
        # If the evaluation data was a file instead of a dataset, the `train`
        # recipe loads it into a temporary dataset named `__train_...` and
        # deletes it after training, so it can't be read here.
        analysis_ready = False
        analysis_block = mo.callout(
            mo.md("""
    **The evaluation data of this run is no longer available.**

    The run was evaluated on a file, which the `train` recipe loads into a
    temporary dataset and deletes after training. To analyze errors, train
    with the evaluation data saved as a dataset.
    """),
            kind="warn",
        )
    elif not eval_datasets:
        analysis_ready = False
        eval_split = corpora.get("eval_split")
        held_out = (
            f"{eval_split:.0%}" if isinstance(eval_split, (int, float)) else "part"
        )
        analysis_block = mo.callout(
            mo.md(f"""
    **This run has no evaluation dataset.**

    Instead of using a separate evaluation dataset, the run held back
    {held_out} of the training data for evaluation. The examples in that split
    can only be rebuilt if the training datasets haven't changed since, and
    this notebook can't check that. To analyze errors, train with a separate
    evaluation dataset.
    """),
            kind="warn",
        )
    else:
        analysis_ready = True
        joined = ", ".join(f"`{d}`" for d in eval_datasets)
        analysis_block = mo.md(f"Evaluated on {joined}.")
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
