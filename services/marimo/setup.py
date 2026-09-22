#!/usr/bin/env python
# fmt: off

from pathlib import Path

import setuptools

PWD = Path(__file__).parent


def setup_package():
    package_name = "ellf_notebook"
    root = PWD.resolve()

    # Read in package meta from about.py
    about_path = root / package_name / "about.py"
    with about_path.open("r", encoding="utf8") as f:
        about = {}
        exec(f.read(), about)

    # Read in requirements and split into packages and URLs
    requirements_path = root / "requirements.in"
    with requirements_path.open("r", encoding="utf8") as f:
        requirements = [
            line.strip()
            for line in f
            if line.strip() and not line.strip().startswith("#")
        ]

    setuptools.setup(
        name=package_name,
        description=about["__summary__"],
        author=about["__author__"],
        author_email=about["__email__"],
        url=about["__uri__"],
        version=about["__version__"],
        license=about["__license__"],
        packages=setuptools.find_packages(exclude=["tests"]),
        install_requires=requirements,
        # The starter notebooks and the offline sample rows are read via
        # __file__ and copied into the workspace at start time.
        package_data={package_name: ["notebooks/*.py", "data/*.jsonl"]},
        include_package_data=True,
        zip_safe=False,
        entry_points={
            # Add the recipe modules under the `ellf_recipes` entry point to ensure
            # the recipe declarations can be imported and indexed.
            "ellf_recipes": [
                f"{package_name} = {package_name}.recipes"
            ],
        },
    )

if __name__ == "__main__":
    setup_package()
