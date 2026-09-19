# ![logo](https://github.com/robertfmath/create-intro-cards/blob/main/docs/source/_static/images/logo_create-intro-cards.svg?raw=true)

<div align="center">

[![CI Status](https://github.com/robertfmath/create-intro-cards/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/robertfmath/create-intro-cards/actions/workflows/ci.yml)
[![PyPI Latest Release](https://img.shields.io/pypi/v/create-intro-cards.svg)](https://pypi.org/project/create-intro-cards/)
[![License](https://img.shields.io/badge/License-BSD_3--Clause-f72d23.svg)](https://github.com/robertfmath/create-intro-cards/blob/main/LICENSE.txt)
[![Documentation](https://img.shields.io/badge/Documentation-e3e300)](https://robertfmath.github.io/create-intro-cards)

</div>

`create-intro-cards` is a Python package that converts a dataset of individuals' names, photos, and custom attributes into a PDF of “intro cards” that describe each individual—all with a single function call. Each intro card displays a person's name, a photo, and a series of attributes based on custom columns in the dataset.

<p align="center">
  <img src="https://github.com/robertfmath/create-intro-cards/blob/main/docs/source/_static/images/example_output_page.png?raw=true" alt="An example of one page of output in the PDF" style="max-width: 100%; height: auto;">
</p>

The input is a Pandas DataFrame, where rows represent individuals and columns their attributes. Columns containing individuals' first names, last names, and paths to photos are required, but the content (and number) of other columns can be freely customized.

<p align="center">
  <img src="https://github.com/robertfmath/create-intro-cards/blob/main/docs/source/_static/images/example_people_data.png?raw=true" alt="An example of the structure of the input Pandas DataFrame" style="max-width: 100%; height: auto;">
</p>

These custom columns are used to generate a series of "column name: attribute value" pairings (e.g., "Hometown: New York, NY") for each individual, which appear below their name on their intro card. If an individual doesn't have a value listed for any custom column, that column's "column name: attribute value" pairing is omitted from their card.

The generated PDF contains all individuals' intro cards, arranged four per page. It's a simple way to transform a dataset of individuals' attributes&mdash;collected from sources such as surveys&mdash;into a fun, easily shareable visual summary.

## Dependencies

- NumPy
- Pandas
- Matplotlib
- Pillow
- ipykernel

All dependencies and their version constraints are declared in `pyproject.toml`. Development tools (Ruff, docformatter, Sphinx, pypdf) are specified in the `[dependency-groups]` section and can be installed with `uv sync --group dev`.

## Installation

With Python 3.11+ installed, run:

```bash
pip install create-intro-cards
```

## Usage

The entry point of the package is the function `make_pdf`, which generates a PDF containing intro cards for all the individuals in the input Pandas DataFrame. The function is passed this DataFrame; the names of the columns in the DataFrame that house first names, last names, and paths to individuals' photos; a path to a default photo to use in the event an individual doesn't have a photo path listed; and a path to the directory in which to store the output.

```python
from create_intro_cards import make_pdf
import pandas as pd

people_data = pd.read_csv("path/to/people/data.csv")

make_pdf(
    people_data,
    "First Name",
    "Last Name",
    "Photo Path",
    "path/to/default/photo.png",
    "path/to/output/dir"
)
```

The output directory will contain the PDF, PNG images of each page of the PDF, and a log file indicating the names and photo availability statuses of all individuals who had an intro card created. The entire process typically takes only a few minutes or less, depending on the number of individuals, number of custom attributes, photo sizes, and hardware.

`make_pdf` also provides a host of optional keyword arguments to tweak the default layout of the intro cards, from font sizes and text placement to photo boundaries and more.

```python
make_pdf(
    people_data,
    "First Name",
    "Last Name",
    "Photo Path",
    "path/to/default/photo.png",
    "path/to/output/dir",
    figure_size=(20, 10),
    name_x_coord=0.40,
    name_y_coord=0.95,
    name_font_size=50,
    desc_padding=0.05,
    desc_font_size=14,
    photo_axes_bounds=(0.01, 0.02, 0.2, 0.92)
)
```

To see how the different keyword arguments affect the appearance of the intro cards, a utility function called `make_pdf_preview` is provided. This function, which must be run in a Jupyter environment, displays a mock-up of the first page of the PDF that would otherwise be created if `make_pdf` were run with the same arguments (minus `path_to_output_dir`). Because it processes only a subset of the dataset, it runs significantly faster than `make_pdf` and is ideal for prototyping.

```python
make_pdf_preview(
    people_data,
    "First Name",
    "Last Name",
    "Photo Path",
    "path/to/default/photo.png",
    figure_size=(20, 10),
    name_x_coord=0.40,
    name_y_coord=0.95,
    name_font_size=50,
    desc_padding=0.05,
    desc_font_size=14,
    photo_axes_bounds=(0.01, 0.02, 0.2, 0.92)
)
```

## Documentation

For full documentation, please see [here](https://robertfmath.github.io/create-intro-cards).
