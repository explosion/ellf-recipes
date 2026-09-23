# marimo notebook service

This package contains a custom recipe that runs a [marimo](https://marimo.io)
notebook as an Ellf service. Project members can open the notebook from the web
app, edit its code and queries and see the charts update. The notebook runs on
your cluster, next to the Prodigy database and behind Ellf's authentication.

The package doesn't depend on the Ellf source tree. It has its own `setup.py`
and requirements and is published the same way as any other custom recipe
package.

> **Important.** Anyone who can open this service can run any Python code on
> your cluster, as the user who started the service. This is how notebooks
> work, so the recipe is limited to project members by default. To share a
> notebook with a wider audience, use the read-only mode.

```
services/marimo/
├── setup.py                            # standard custom recipe packaging
├── requirements.in                     # marimo, installed into the image on publish
└── ellf_notebook/
    ├── recipes/marimo_notebook.py      # the service, a notebook runner
    ├── types.py                        # the notebook asset type
    ├── launcher.py                     # starting marimo
    ├── workspace.py                    # where working copies live on NFS
    ├── data.py                         # Prodigy and Ellf SDK plumbing
    ├── notebooks/dataset_explorer.py   # annotations in a dataset
    ├── notebooks/training_results.py   # scores and error analysis
    └── notebooks/blank.py              # reaching datasets, assets and jobs
```

## What it demonstrates

- **A custom service recipe with its own dependency.** `marimo` isn't included
  in the base recipes image. `ellf publish code` reads it from the package
  metadata, the broker installs it on the cluster and the result is added to a
  new image as a layer. You don't need a Dockerfile or a local build.
- **A service that runs its own server.** The recipe starts marimo's server and
  returns `None`. The SDK keeps the process running while the cluster routes
  requests to marimo's port and checks its health. The built-in Streamlit
  dashboard works the same way.
- **Editable code that persists.** The notebook is a `.py` file on the shared
  NFS volume, not in the image. Changes made in the browser are kept after the
  service stops, the image is rebuilt or the package is published again.
- **Data access without setup.** The service already has the Prodigy database
  connection and a token for the user who started it. Reading a dataset takes
  one call, and listing what's on your cluster takes two.

## Publish and run

```bash
cd services/marimo
pip install -e .
ellf publish code . --package-version 0.1.0
```

`ellf publish code` runs whichever `python` is first on your `PATH`, so
activate the environment instead of calling the CLI by its absolute path. The
package also needs to be importable from that environment, so run
`pip install -e .` first or set `PYTHONPATH=$PWD`. A directory with a
`setup.py` is published as a distribution, and its metadata is built by
importing it.

The first publish spends a few minutes on `Installing requirements on the
cluster`, which installs marimo. The install is cached on NFS for each base
image and set of requirements, so publishing again with the same dependencies
skips this step.

Publishing registers the recipe but not the notebooks, so the notebook picker
is empty at first. A notebook asset is a file on shared storage that's
registered with Ellf. You can register the included notebooks, or your own,
with two commands.

```bash
ellf files cp ellf_notebook/notebooks/dataset_explorer.py \
    "{__nfs__}/marimo/starters/dataset_explorer.py" --make-dirs
ellf assets create dataset_explorer \
    "{__nfs__}/marimo/starters/dataset_explorer.py" --kind notebook
```

Repeat this for `training_results.py` and `blank.py`, or for any other notebook
you want to add to the picker. You only need `--make-dirs` the first time, to
create the folder. `ellf assets create` only stores a reference to the file and
doesn't copy any data, so the file has to be on shared storage before you
register it. If you copy a new version of a notebook with `--overwrite`, new
workspaces start from the new version and existing working copies stay the
same.

You can then start a service with any of the registered notebooks.

```bash
ellf services create marimo_notebook --help
ellf services create marimo_notebook --name explore --notebook dataset_explorer --workspace team-a
ellf services url explore
```

You can also create the service in the web app, where the recipe is listed
under Services with a form based on its arguments. When you open the service
URL as a logged in project member, the notebook opens in your browser.

The `workspace` argument is the name of the folder on shared storage that holds
the working copy of the notebook. To continue where you or a colleague left off,
use the same workspace name. To start from the notebook as it was registered,
use a new name. The `read_only` argument serves the notebook as an app instead
of an editor, so you can share a finished analysis with people who shouldn't
change it.

## Notebooks are assets

The service only runs notebooks. Its form asks which notebook to open and where
to keep the working copy. If a notebook needs anything else, like a dataset to
read or a training run to report on, it asks for it on the page, using the Ellf
SDK.

If the service form asked for these instead, it would need the same arguments
for every notebook. Each notebook can offer exactly the inputs it needs as
marimo widgets, for example a dataset, a date range and two thresholds, and you
can change them without publishing the package again.

Notebooks are registered as assets, so the picker lists the notebooks on your
cluster, not only the ones in this repository. When you register your own
notebook, it's listed in the picker next to these.

| Notebook | Description |
| --- | --- |
| `dataset_explorer` | Shows the annotations in a dataset as a table you can filter, with statistics and charts. This is the most complete example, so it's a good place to start. |
| `training_results` | Shows the scores of a training run from the `kind="results"` asset that the `train` recipe creates, and the examples the trained pipeline gets wrong. |
| `blank` | Shows how to access datasets, assets and jobs on your cluster, with a working example for each. |

The registered asset is the source of the notebook. The service copies it into
the workspace the first time the notebook is opened and never overwrites that
copy, so each workspace has its own working copy and people using different
workspaces don't overwrite each other's changes. If you register a new version
of a notebook, new workspaces start from that version and existing ones stay
the same.

### Selecting data in charts

The analysis notebooks create their charts with `mo.ui.altair_chart`, which
lets you select data in a chart and use the selection in Python. The
`chart.value` attribute is a dataframe with the rows you clicked or brushed,
and the table below the chart uses it. In the dataset explorer, you can click a
label to only show annotations with that label. In the training results, you
can click a bar in the errors chart to see those errors.

To make your own charts selectable, use `mo.ui.altair_chart(chart)` instead of
`chart`.

## Using the dataset explorer

The cells in the dataset explorer load a dataset, convert the annotations to a
table, filter them and then visualize the results.

1. At the top, you can choose a dataset and how often to reload it. The list
   shows the datasets that the user who started the service has access to. If
   you set a reload interval, new annotations are shown as they come in.
2. The cell marked **the query** converts each annotation into one row of a
   table, with the columns you want to filter and group by. Start here to
   change the notebook, for example to add a value from `meta`, a score or a
   token count.
3. The filters for labels, annotators and decisions are based on the columns
   the query creates.
4. The charts and table show the filtered annotations. You can search the
   table and download it.
5. The last cell uses the Ellf SDK to list the datasets on your cluster, as
   the user who started the service.

When you change a cell, marimo runs all cells that depend on it again. This
means the notebook never shows results from an earlier version of the code,
which is why this service uses marimo instead of Jupyter.

To work on another notebook in the same workspace, start another service with
that notebook and the same workspace name, or open it in marimo's file browser.

## How it works

**Routing.** Requests to the service are routed through `/services/{job_id}/`,
and Traefik removes that prefix before the request reaches the service. This
means marimo is served from its own root and doesn't need `--base-url`. marimo's
HTML uses relative paths like `./assets/...` and its frontend builds all API
and websocket URLs from `document.baseURI`, so the prefix is kept in the
browser. If a future version of marimo changes this, you can set `--base-url`
and add a matching ingress rule.

**Authentication.** The recipe sets `auth="session"`, so the ingress only lets
in project members who are logged in to the web app. marimo's own token
authentication is turned off, because it would ask users for a second password
after they're already authenticated.

**Persistence.** `workspace.py` resolves `{__nfs__}/marimo/<workspace>/` using
`ELLF_BUILTIN_PATH_NFS`, which the broker sets on every recipe pod. The
notebook asset's file is copied into the workspace the first time the service
starts. After that, the working copy is never overwritten, so changes made in
the browser are kept when the service restarts, the image is rebuilt or the
package is published again. Registered notebooks are stored in
`{__nfs__}/marimo/starters/`, next to the workspaces, because they don't belong
to any one workspace.

**Credentials.** The service's environment already includes
`PRODIGY_CONFIG_OVERRIDES` with the database connection and `ELLF_PAM_*` with a
short-lived token for the user who started the service. The recipe passes the
whole environment on to the marimo process, so the notebooks don't need any
configuration.

## Develop locally

Install the package and the development requirements. `requirements.in` only
lists what the cluster image doesn't include, so the recipes SDK and pytest are
listed in `requirements-dev.in` and aren't installed by `pip install -e .`.

```bash
pip install -e .
pip install -r requirements-dev.in
```

To edit one of the included notebooks, open it with marimo.

```bash
marimo edit ellf_notebook/notebooks/dataset_explorer.py
```

When you run a notebook locally, there's no Prodigy database or job token, so
the notebooks can't read any datasets. Instead, they show an error that
explains why the dataset couldn't be read and how to fix it. To read real
annotations locally, set `PRODIGY_CONFIG_OVERRIDES` or a `prodigy.json` to
point Prodigy to a database you can reach.

To see the form the recipe generates for creating a service, without starting
it, use `ellf-dev preview`.

```bash
ellf-dev preview marimo_notebook
```

`ellf-dev preview` shows the form and prints the arguments it would submit. It
never calls the recipe, so nothing is started. To test the recipe itself,
publish it to your cluster.

If you edit one of the included notebooks, register it again to use the new
version in new workspaces. Changes you make in the browser only affect that
workspace.

To run the tests, use pytest.

```bash
python -m pytest tests -q
```

## Limitations

- Each service runs one notebook with one marimo kernel. The service is meant
  for one person at a time, not for many users sharing compute. If two people
  edit the same workspace at the same time, their changes can overwrite each
  other.
- When the service stops, only the notebook file is kept, not the kernel state.
  To keep results, write them to the workspace directory, which is on NFS.
- `requirements.in` only lists what the base image doesn't include. The cluster
  installs the requirements with `pip install --target`, which ignores the
  packages already in the image, and the broker then packs the result into an
  image layer. Every extra requirement adds build time and increases the image
  size. That's why `ellf-recipes-sdk` is listed in `requirements-dev.in`
  instead. The base image already includes it, and listing it here would also
  install spaCy, boto3, google-cloud and psycopg2. The same applies to `pandas`
  and `altair`.
- The broker builds the image layer in its event loop, and its liveness probe
  allows about 90 seconds without a response. A large set of requirements can
  block the broker long enough for it to be restarted while publishing, which
  shows up as a read timeout or a 503 error from `POST /api/v1/envs/builds`.
  Keep the requirements as small as possible to avoid this.
