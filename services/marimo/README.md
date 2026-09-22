# marimo notebook service

A custom recipe package that runs a [marimo](https://marimo.io) notebook as an
Ellf service. Project members open it from the web app, edit the code and the
queries in place, and watch the charts recompute, all inside the cluster, next
to the Prodigy database and behind the platform's auth.

Nothing here touches the Ellf source tree. It is a standalone package with its
own `setup.py` and its own requirements, published the way any customer would
publish their own recipes.

> ✨ **Important note.** Anyone who can open this service can run arbitrary
> Python inside your cluster, as the user who started the job. That is what a
> notebook is. It is why the recipe is limited to project members by default,
> and why a read-only mode exists for a wider audience.

```
services/marimo/
├── setup.py                            # standard custom-recipe packaging
├── requirements.in                     # marimo, installed into the image on publish
└── ellf_notebook/
    ├── recipes/                        # one @service_recipe per notebook
    ├── launcher.py                     # starting marimo, shared by all three
    ├── workspace.py                    # where editable notebooks live on NFS
    ├── data.py                         # Prodigy and Ellf SDK plumbing
    ├── notebooks/dataset_explorer.py   # starter for annotations in a dataset
    ├── notebooks/training_results.py   # starter for scores and error analysis
    ├── notebooks/blank.py              # starter for datasets, assets and jobs
    └── data/sample_annotations.jsonl   # off-cluster fallback rows
```

## What it demonstrates

- **A custom service recipe with its own dependency.** `marimo` isn't in the
  base recipes image. `ellf publish code` reads it off the package metadata,
  the broker pip-installs it on the cluster inside the base image, and the
  result is layered into a new image. No Dockerfile, no local build.
- **A port-mode service.** The recipe starts marimo's own server and returns
  `None`, and the SDK keeps the process alive while the cluster routes and
  health-checks marimo's port. Same shape as the built-in Streamlit dashboard.
- **User-editable code that survives.** The notebook is a plain `.py` on the
  shared NFS volume, not in the image. Edits made in the browser outlive the
  service, an image rebuild, and a republish of this package.
- **Data access without setup.** The pod already has the Prodigy database
  connection and a job token for the user who started it, so reading a dataset
  is one call and listing what's on the cluster is two.

## Publish and run

```bash
cd services/marimo
pip install -e .
ellf publish code . --package-version 0.1.0
```

`ellf publish code` shells out to whatever `python` resolves to on `PATH`, so
activate the environment rather than calling the CLI by absolute path, and make
sure the package is importable from it. Either `pip install -e .` first, or
`PYTHONPATH=$PWD`. A directory with a `setup.py` is published as a
distribution, and a distribution is expected to be importable when its metadata
is built.

The first publish spends a few minutes on `Installing requirements on the
cluster`, which is marimo. The install is cached on NFS by base image and
requirement set, so republishing unchanged dependencies skips it.

```bash
ellf services create dataset_explorer --help
ellf services create dataset_explorer --name explore --dataset support_ner --workspace team-a
ellf services url explore
```

Or create it from the web app, where the recipe shows up under Services with a
form built from its signature. Open the URL as a logged-in project member and
the notebook is there.

Every recipe takes a `workspace`, which is the folder on shared storage that
holds its notebooks, and a `read_only` switch that serves the notebook as an
app rather than an editor. Reuse a workspace name to pick up where you or a
colleague left off, or pick a new one for a clean slate.

## The recipes

Three, because the notebooks want different inputs. Each one is a named
service that opens its own notebook, so you pick the analysis you want rather
than a generic notebook and then a filename.

| Recipe | Asks for | What you get |
| --- | --- | --- |
| `dataset_explorer` | a dataset | The annotations in it. Flatten, filter, chart, browse. The worked example, so start here. |
| `training_results` | a model and a dataset | What the training run scored, then which examples the model gets wrong. Metrics come from the `kind="results"` asset the `train` recipe writes beside every pipeline, and the pipeline itself is what the error analysis runs. |
| `marimo_notebook` | a dataset and a filename | The general case. Open a notebook somebody wrote in a workspace, or start a new one. A name that isn't there yet is created from a blank starter that shows how to reach datasets, assets and jobs. |

The notebooks themselves ship in `notebooks/`. `seed_notebook` copies one into
the workspace the first time it is opened and never overwrites it again, so a
starter is a starting point rather than a managed file. Once you are in,
marimo's file browser is rooted at the workspace, so you can switch between
notebooks regardless of which recipe opened the session.

### Charts are inputs, not output

Both analysis notebooks wrap their charts in `mo.ui.altair_chart`. That makes a
chart's selection a Python value. `chart.value` is a dataframe of exactly the
rows you clicked or brushed, and the table below reads it. Click a label bar in
the explorer and the annotation table narrows to that label. Click a bar in the
error chart and you get those specific mistakes.

This is the thing a notebook does that a dashboard doesn't, and it is one line
of difference. Write `mo.ui.altair_chart(chart)` instead of `chart`.

## Using the explorer

The starter notebook is ordered the way you'd work, from connect to shape to
filter to look.

1. The dataset name and an auto-refresh interval sit at the top. Annotation
   happening right now shows up on the next refresh.
2. **The query** is one cell that flattens each Prodigy annotation into the
   columns you want to slice by. This is the cell to edit first. Add a field
   from `meta`, pull out a score, count tokens.
3. Filters for labels, annotators and decisions, driven by whatever the query
   produced.
4. Charts and a searchable, downloadable table.
5. A last cell that asks the platform rather than the annotation database what
   is on the cluster, through the Ellf SDK, authenticated as you.

Everything is reactive, so changing a cell re-runs every cell that depends on
it. There is no hidden state to get out of sync, which is the reason for marimo
over Jupyter here.

To start a second notebook in the same workspace, create another service with a
different `notebook` value, or use marimo's file browser, since the process's
working directory is the workspace.

## How it works

**Routing.** The public route is `/services/{job_id}/` and Traefik strips that
prefix before the request reaches the pod, so marimo is served at its own root
with no `--base-url`. Its HTML references assets relatively as `./assets/...`
and its frontend derives every API and websocket URL from `document.baseURI`,
so the prefix survives the round trip. If a future marimo changes that,
`--base-url` plus a matching ingress rule is the fallback.

**Auth.** `auth="session"` gates the route at the ingress, so logged-in project
members get in from the web app and nobody else does. marimo's own token auth
is turned off rather than layered on top, where it would be a second password
prompt on an already authenticated route.

**Persistence.** `workspace.py` resolves `{__nfs__}/marimo/<workspace>/` from
`ELLF_BUILTIN_PATH_NFS`, which the broker sets on every recipe pod and mounts
read-write. Starter notebooks are copied in once, on first start. After that
the file on NFS is the source of truth and is never overwritten.

**Credentials.** The pod's environment already carries
`PRODIGY_CONFIG_OVERRIDES` for the database connection and `ELLF_PAM_*` for a
short-lived token belonging to the user who started the job. The recipe passes
the whole environment through to the marimo subprocess, which is why the
notebook's first cells need no configuration.

## Develop locally

Install the package and the development requirements. `requirements.in` lists
only what the cluster image lacks, so the recipes SDK and pytest live in
`requirements-dev.in` instead and are not pulled in by `pip install -e .`.

```bash
pip install -e .
pip install -r requirements-dev.in
```

Work on a starter notebook directly. `ELLF_MARIMO_ROOT` keeps the workspace out
of the checkout.

```bash
ELLF_MARIMO_ROOT=/tmp/nb marimo edit ellf_notebook/notebooks/dataset_explorer.py
```

The notebook falls back to bundled sample rows when there is no Prodigy
database and no job token, and says so in a banner on the page, so it opens and
renders on a laptop.

To see the service-creation form the recipe generates, without running it.

```bash
ellf-dev preview marimo_notebook
```

`preview` renders the form and prints the arguments it would submit. It never
calls the recipe, so nothing starts. To see the recipe actually do its job,
publish it to a cluster, where the dataset argument resolves to a real dataset
and the notebook reads real annotations.

Editing a starter changes what new workspaces get. Editing in the browser
changes only that workspace.

```bash
python -m pytest tests -q
```

## Limits worth knowing

- One notebook per service and one marimo kernel per notebook. This is a
  workbench for a person rather than a multi-tenant compute service. Two people
  editing the same workspace at the same time will fight over the file.
- A notebook's work is lost when the service stops, and only the file persists,
  not the kernel state. Write anything you want to keep to the workspace
  directory, which is on NFS.
- `requirements.in` lists only what the base image lacks. The cluster-side
  install is `pip install --target`, which ignores the image's own
  site-packages, and the broker then tars and gzips the whole result into a
  layer, so every redundant line costs build time and image size. That is why
  `ellf-recipes-sdk` sits in `requirements-dev.in`, because the base image has
  it and listing it would pull in spacy, boto3, google-cloud and psycopg2 for
  nothing. Same reasoning for `pandas` and `altair`.
- Layer assembly happens inside the broker's event loop, and the broker's
  liveness probe allows about 90 seconds of unresponsiveness. A fat requirement
  set can block it long enough to get the broker restarted mid-publish, which
  shows up as a read timeout or a 503 from `POST /api/v1/envs/builds`. Keeping
  the requirement set lean is not just tidiness.
