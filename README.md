<a href="https://explosion.ai"><img src="https://explosion.ai/assets/img/logo.svg" width="125" height="125" align="right" /></a>

<img src=".github/ellf.svg" width="120" alt="Ellf" />

# Ellf Recipes

This repository contains a collection of recipes for
[Ellf](https://ellf.ai), your virtual NLP engineer for agentic development.
Ellf runs on a cluster you control — your own cloud or your own machine — so
your data never leaves it. In order to use this repo you'll need an Ellf
cluster and a [Prodigy](https://prodi.gy) license, since the recipes here read
and write annotations. For questions and bug reports, use `ellf support create`
or the [Prodigy Support Forum](https://support.prodi.gy). If you've found a
mistake or bug, feel free to submit a
[pull request](https://github.com/explosion/ellf-recipes/pulls).

> ✨ **Important note:** Nothing in this repository is bundled into Ellf. These
> recipes are published to your own cluster when you want them, and they're
> written to be read and rewritten — commented more heavily than the built-ins,
> and kept simple so they work as the basis for your own. A recipe you fork is
> working as intended.

## 📋 Usage

A recipe here is an ordinary Python package. Publishing one builds an image on
your cluster and registers the recipe, after which it appears in the web app
alongside the built-ins:

```bash
cd services/marimo
pip install -e .
ellf publish code . --package-version 0.1.0
```

Then start it from the web app, or from the terminal:

```bash
ellf services create marimo_notebook --name notebook --dataset your_dataset
ellf services url notebook
```

Every recipe takes `--help`, which lists the arguments it accepts:

```bash
ellf services create marimo_notebook --help
```

To work on a recipe before publishing it, the recipes SDK ships a dev CLI:

```bash
ellf-dev preview marimo_notebook   # the creation form the recipe generates
ellf-dev run marimo_notebook       # run it locally
python -m pytest tests -q
```

### Some things to try

The recipes are yours to edit. Starting points:

- Open `dataset_explorer.py` and change **the query cell** — pull a field out
  of `meta`, count tokens, extract a score. Everything downstream recomputes.
- Swap `mark_bar` for `mark_point` in a chart, or add a facet.
- Wrap a chart in `mo.ui.altair_chart` and it becomes an *input*: clicking it
  filters the table below.
- Add a cell that lists the assets on your cluster and reads one — see the
  `blank.py` starter for the three lines that takes.
- Add your own notebook to `ellf_notebook/notebooks/`; it becomes a starter
  anyone can open by filename.
- Serve a finished analysis read-only (`--read-only`) and hand it to people who
  shouldn't be editing it.

## 🍳 Recipes

### Services

Long-running things people open in a browser, behind the platform's auth.

| Recipe | Description |
| ------ | ----------- |
| [`marimo_notebook`](services/marimo) | A [marimo](https://marimo.io) notebook running on your cluster, next to the annotation database and authenticated as you. Notebooks live on shared storage, so edits in the browser outlive the service. Ships starters for exploring a dataset, reading training results and doing error analysis. |

Tasks (annotation interfaces), actions (batch jobs) and agents belong here too
— open a PR if you've written one worth sharing.

## 📚 What's in a recipe

Each directory is a self-contained, installable package:

```
services/marimo/
├── setup.py               # declares the `ellf_recipes` entry point
├── requirements.in        # only what Ellf's base image lacks
├── ellf_notebook/
│   ├── recipes/           # the @service_recipe itself
│   ├── data.py            # the wiring: datasets, assets, jobs, SDK client
│   └── notebooks/         # starters, meant to be rewritten
└── tests/                 # run without a cluster
```

The recipe is wiring; the interesting part is usually what it hands you. In
`services/marimo` that's `data.py` — reaching a Prodigy dataset, an
authenticated SDK client, assets and the cluster's jobs — and the notebooks are
examples of using it.

Recipe requirements are installed on the cluster at publish time with
`pip install --target`, which ignores what the base image already has. Anything
in a `requirements.in` here is therefore downloaded in full and tarred into an
image layer, so these files list only what's genuinely missing. Check before
you add.

## 📄 License

The recipe code in this repository is MIT licensed. Ellf and Prodigy are
commercial products and are not.
