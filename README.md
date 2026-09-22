<a href="https://explosion.ai"><img src="https://explosion.ai/assets/img/logo.svg" width="100" height="100" align="right" /></a>

<img src=".github/ellf.svg" width="120" alt="Ellf" />

# Ellf Recipes

This repository contains a collection of recipes for
[Ellf](https://beta.ellf.ai), a platform for agentic NLP development. To use
them you'll need an Ellf cluster and a license, since the recipes read and write
annotations that live on the cluster itself. For questions and bug reports,
use `ellf support create` from your Ellf CLI.

> ✨ **Important note.** Nothing in this repository is bundled into Ellf. These
> recipes are published to your own cluster on demand, and they're written to
> be read and rewritten. They carry more comments than the built-ins and stay
> deliberately simple, so they work as the basis for your own.

## 📋 Usage

A recipe here is an ordinary Python package. Publishing one builds an image on
your cluster and registers the recipe, after which it appears in the web app
alongside the built-ins.

```bash
cd services/marimo
pip install -e .
ellf publish code . --package-version 0.1.0
```

Then start it from the web app, or from the terminal.

```bash
ellf services create marimo_notebook --name notebook --dataset your_dataset
ellf services url notebook
```

Every recipe takes `--help`, which lists the arguments it accepts.

```bash
ellf services create marimo_notebook --help
```

To work on a recipe before publishing it, the recipes SDK ships a dev CLI.

```bash
ellf-dev preview marimo_notebook   # the creation form the recipe generates
ellf-dev run marimo_notebook       # run it locally
python -m pytest tests -q
```

### Some things to try

Start the notebook from the **Services** page in the web app and open it.
Everything here happens in the browser, and your edits are saved to shared
storage, so they outlive the service.

- Edit **the query cell**, the one that flattens each annotation into columns.
  Pull a field out of `meta`, count tokens, extract a score. Every cell below
  it recomputes.
- Change a chart. Swap `mark_bar` for `mark_point`, or add a facet.
- Wrap a chart in `mo.ui.altair_chart` and it turns into an input, so clicking
  a bar filters the table below it.
- Add a cell that lists the assets on your cluster and reads one.

The creation form is worth playing with too.

- Put a name you haven't used in **Notebook file** and you get a blank
  notebook, already wired up, with working examples for datasets, assets and
  jobs.
- Reuse a **Workspace** name to pick up where a colleague left off, or pick a
  new one for a clean slate.
- Tick **Share as a read-only app** to hand a finished analysis to people who
  shouldn't be editing it.

To add a starter everyone can open, put your notebook in
`ellf_notebook/notebooks/` and publish the package again.

## 🍳 Recipes

### Services

Long-running services people open in a browser, behind the Ellf auth.

| Recipe | Description |
| ------ | ----------- |
| [`marimo_notebook`](services/marimo) | A [marimo](https://marimo.io) notebook running on your cluster, next to the annotation database and authenticated as you. Notebooks live on shared storage, so edits in the browser outlive the service. Ships starters for exploring a dataset, reading training results and doing error analysis. |

## 📚 What's in a recipe

Each directory is a self-contained, installable package.

```
services/marimo/
├── setup.py               # declares the `ellf_recipes` entry point
├── requirements.in        # only what Ellf's base image lacks
├── ellf_notebook/
│   ├── recipes/           # the @service_recipe itself
│   ├── data.py            # wiring for datasets, assets, jobs, SDK client
│   └── notebooks/         # starters, meant to be rewritten
└── tests/                 # run without a cluster
```

The recipe is wiring, and the interesting part is usually what it hands you. In
`services/marimo` that part is `data.py`, which reaches a Prodigy dataset, an
authenticated SDK client, assets and the cluster's jobs. The notebooks are
examples of using it.

Recipe requirements are installed on the cluster at publish time with
`pip install --target`, which ignores what the base image already has. Anything
in a `requirements.in` here is therefore downloaded in full and tarred into an
image layer, so these files list only what's genuinely missing.

## 📄 License

The recipe code in this repository is MIT licensed. Ellf and Prodigy are
commercial products and are not.
