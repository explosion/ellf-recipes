# ellf-recipes

Open-source recipes for the [Ellf](https://ellf.ai) platform.

Each directory here is a self-contained, installable Python package holding one
recipe. Nothing is bundled into the platform's images: you publish a recipe to
your own cluster when you want it, and you are expected to fork and edit it.
That is the point — these are starting points that happen to work, not products.

## Recipes

| Recipe | Kind | What it does |
| --- | --- | --- |
| [`services/marimo`](services/marimo) | service | A [marimo](https://marimo.io) notebook running on your cluster, next to the annotation database and behind the platform's auth. Ships starters for dataset exploration, training results and error analysis. |

## Using one

Publishing builds an image on your cluster and registers the recipe, after
which it appears in the web app like any built-in:

```console
$ cd services/marimo
$ pip install -e .
$ ellf publish code . --package-version 0.1.0
```

To work on a recipe before publishing it, the recipes SDK has a dev CLI:

```console
$ ellf-dev preview <recipe-name>    # the service-creation form it generates
$ ellf-dev run <recipe-name>        # run it locally
$ python -m pytest tests -q
```

## A note on dependencies

Recipes run inside Ellf's base image and their requirements are installed on
the cluster at publish time with `pip install --target`, which ignores what the
image already has. Anything listed in a `requirements.in` here is therefore
downloaded in full and tarred into an image layer — so these files list only
what the base image genuinely lacks. Before adding a dependency, check whether
it is already there.

## Requirements

These recipes import `prodigy` and are meant to run on an Ellf cluster, which
requires a Prodigy licence. The recipe code in this repository is MIT
licensed; the platform and Prodigy are not.

## Contributing

Issues and pull requests welcome. A recipe is easier to accept if it has tests
that run without a cluster, degrades gracefully when the data it expects isn't
there, and explains in its README what it demonstrates rather than only what it
does.
