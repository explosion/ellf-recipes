<a href="https://explosion.ai"><img src=".github/explosion.svg" width="100" alt="Explosion" align="right" /></a>

<img src=".github/ellf.svg" width="120" alt="Ellf" />

# Ellf Recipes

This repository contains a collection of recipes for
[Ellf](https://beta.ellf.ai), a platform for agentic NLP development. To use
them, you need an Ellf cluster and a license, because the recipes read and
write annotations stored on your cluster. For questions and bug reports, run
`ellf support create` in the Ellf CLI.

> ✨ **Important note.** The recipes in this repository aren't included in Ellf.
> You publish them to your own cluster when you need them. They have more
> comments than the built-in recipes and are kept simple, so you can use them
> as a starting point for your own.

## 📋 Usage

Each recipe is a Python package. When you publish it, Ellf builds an image on
your cluster and registers the recipe, so it's listed in the web app next to
the built-in recipes.

```bash
cd services/marimo
pip install -e .
ellf publish code . --package-version 0.1.0
```

The marimo service opens notebooks that are registered as assets, so register
at least one notebook before you start it. The
[service README](services/marimo/README.md) explains how to register the
included notebooks. You can then start the service in the web app, or from the
command line.

```bash
ellf services create marimo_notebook --name explore --notebook dataset_explorer
ellf services url explore
```

To see the arguments a recipe accepts, use `--help`.

```bash
ellf services create marimo_notebook --help
```

To see the form a recipe generates without starting it, use `ellf-dev preview`.
To run the tests, use pytest.

```bash
ellf-dev preview marimo_notebook
python -m pytest tests -q
```

### Some things to try

Start the service from the **Services** page in the web app and open it. You
work in the browser, and your changes are saved to shared storage, so they're
kept after the service stops.

- In the dataset explorer, edit the cell marked **the query**, which converts
  each annotation into a row of a table. Add a value from `meta`, count tokens
  or extract a score. When you run the cell, all cells that depend on it
  update.
- Change a chart, for example by replacing `mark_bar` with `mark_point` or
  adding a facet.
- Wrap a chart in `mo.ui.altair_chart` to make it selectable, so clicking a bar
  filters the table below it.
- Open the `blank` notebook to see how to list the datasets, assets and jobs on
  your cluster.

You can also try the options on the service form.

- To continue where you or a colleague left off, use the same **Workspace**
  name. To start from the notebook as it was registered, use a new name.
- Select **Share as a read-only app** to share a finished analysis with people
  who shouldn't change it.

To add your own notebook, copy it to shared storage and register it as an
asset of kind `notebook`. It's then listed on the service form next to the
included notebooks.

## 🍳 Recipes

### Services

Services run in the background, and people open them in a browser after
logging in to Ellf.

| Recipe | Description |
| ------ | ----------- |
| [`marimo_notebook`](services/marimo) | Runs a [marimo](https://marimo.io) notebook on your cluster, next to the Prodigy database and behind Ellf's authentication. Notebooks are registered as assets, so the form lists the notebooks on your cluster, and each notebook asks for the inputs it needs on the page. Includes notebooks for exploring a dataset and for viewing training results and errors. |

## 📚 What's in a recipe

Each directory is a self-contained package you can install.

```
services/marimo/
├── setup.py               # declares the `ellf_recipes` entry point
├── requirements.in        # only what Ellf's base image doesn't include
├── ellf_notebook/
│   ├── recipes/           # the @service_recipe
│   ├── types.py           # the notebook asset type
│   ├── workspace.py       # where working copies are stored
│   ├── data.py            # helpers for datasets, assets, jobs and the SDK client
│   └── notebooks/         # example notebooks to register and adapt
└── tests/                 # run without a cluster
```

The recipe itself only starts the notebook. The interesting part is what the
notebooks can do with it. In `services/marimo`, that's `data.py`, which reads
Prodigy datasets, creates an authenticated SDK client and lists the assets and
jobs on your cluster. The notebooks show how to use it.

When you publish a recipe, its requirements are installed into the recipe image
again, even if the base image already includes them. This adds build time and
increases the image size, so each `requirements.in` only lists what the base
image doesn't include.

## 📄 License

The recipe code in this repository is MIT licensed. Ellf and Prodigy are
commercial products and aren't MIT licensed.
