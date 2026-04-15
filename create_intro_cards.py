from dataclasses import dataclass, field
from datetime import datetime
import glob
import logging
import os
import re
from typing import TypedDict

import matplotlib as mpl
from matplotlib import axes
from matplotlib.text import Text
from matplotlib.transforms import Transform
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from PIL import Image


class StatsDict(TypedDict):
    """Metadata about a given run of the intro card creation process."""

    number_of_cards_created: int
    """The total number of intro cards that were created."""

    number_of_cards_to_create: int
    """The number of people for whom cards needed to be generated."""

    people_with_photo_warnings: list[str]
    """The names of people whose photos could not be found or read."""


@dataclass
class CardLayout:
    """Layout and formatting parameters for intro cards.

    :param figure_size: Width and height of each page figure in inches, defaults to
        (23, 13)
    :type figure_size: tuple[float, float], optional
    :param name_x_coord: Axes-relative x-coordinate of the name (and description) on
        each card, defaults to 0.35
    :type name_x_coord: float, optional
    :param name_y_coord: Axes-relative y-coordinate of the name on each card, defaults
        to 0.95
    :type name_y_coord: float, optional
    :param name_font_size: Font size of the name on each card, defaults to 50
    :type name_font_size: float, optional
    :param desc_padding: Axes-relative padding between the bottom of the name bounding
        box and the top of the description, defaults to 0.05
    :type desc_padding: float, optional
    :param desc_font_size: Font size of the description on each card. Iteratively reduced
        by 5% if the description would overflow the bottom of the card, defaults to 16
    :type desc_font_size: float, optional
    :param photo_axes_bounds: Bounds of the inset photo Axes as (x0, y0, width, height)
        in Axes-relative coordinates, defaults to (0.02, 0.02, 0.3, 0.93)
    :type photo_axes_bounds: tuple[float, float, float, float], optional
    """

    figure_size: tuple[float, float] = (23, 13)
    name_x_coord: float = 0.35
    name_y_coord: float = 0.95
    name_font_size: float = 50
    desc_padding: float = 0.05
    desc_font_size: float = 16
    photo_axes_bounds: tuple[float, float, float, float] = field(
        default_factory=lambda: (0.02, 0.02, 0.3, 0.93)
    )


# Required for ``make_pdf_preview``; matches Agg backend of `savefig` in `make_pdf`
mpl.use("module://matplotlib_inline.backend_inline")

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

_SAVEFIG_DPI = 175
_PREVIEW_DPI = 300
_PDF_RESOLUTION = _SAVEFIG_DPI  # Must match _SAVEFIG_DPI so inch dimensions are preserved
_FONT_SHRINK_FACTOR = 0.95
_BOTTOM_MARGIN = 0.02
_CARDS_PER_PAGE = 4


def make_pdf(
    people_data: pd.DataFrame,
    first_name_col: str,
    last_name_col: str,
    photo_path_col: str,
    path_to_default_photo: str,
    path_to_output_dir: str = "./intro_cards_output",
    layout: CardLayout = CardLayout(),
) -> StatsDict:
    r"""Generate a PDF containing intro cards for all individuals in ``people_data``.

    This is entry point of the package. It generates a PDF, where each page of the PDF
    is a single Matplotlib figure, which is itself composed of four individuals' intro
    cards. Each intro card contains an individual's name, a photo (either provided or
    default), and a description that displays their "column name: attribute value"
    pairings for each custom column in ``people_data`` (i.e., columns not related to
    name and photo path).

    On each intro card, "column name: attribute value" pairings are separated by a new
    line, and each "column name" is rendered in bold. Text on any given line is wrapped
    such that it approaches—but does not touch—the right border of the card. If an
    individual's "attribute value" is left blank, that particular "column name:
    attribute value" pairing will be omitted from their card. Note that if the name of a
    custom column contains ``~``, ``^``, or ``\``, that character will be removed from
    the column name on the intro card.

    This function also provides parameters to tweak the formatting and layout of all
    individuals' intro cards, such as ``name_x_coord``, ``desc_padding``, and
    ``photo_axes_bounds``. Using :func:`make_pdf_preview` (Jupyter environment required)
    allows for quick feedback on how these parameters affect the cards.

    The output PDF is saved down in ``path_to_output_dir``. Also in this directory are
    the constituent pages of the PDF (PNG images of the Matplotlib figures, as rendered
    using the Agg backend) and a log file that denotes the names and photo availability
    statuses of all the individuals who had an intro card created. Depending on the
    number of individuals, the file size of the PDF might be quite large; to reduce it
    (at the expense of resolution), scale down each number in ``figure_size``,
    ``name_font_size``, and ``desc_font_size`` by a common factor.

    The function returns a dictionary with metadata pertaining to the number of intro
    cards that were created, the number of people for whom cards needed to be generated,
    and the names of people whose photos could not be found or read.

    :param people_data: The pandas DataFrame containing all the data from which to make
        intro cards. Rows represent individuals, while columns represent attributes of
        those individuals. The choice of attributes is completely up to the user (e.g.,
        "Hometown", "Fun Fact"), but it is required that there be columns for first
        name, last name, and paths to individuals' photos (which will ultimately be
        displayed on their respective intro cards). The name of each column—except the
        ones for first name, last name, and photo paths—will ultimately end up being
        listed on individuals' intro cards in bold. The order of these columns dictates
        the order in which "column name: attribute value" pairings are displayed on the
        cards.
    :type people_data: pd.DataFrame
    :param first_name_col: The name of the column (Series) in ``people_data`` that
        houses first names
    :type first_name_col: str
    :param last_name_col: The name of the column (Series) in ``people_data`` that houses
        last names
    :type last_name_col: str
    :param photo_path_col: The name of the column (Series) in ``people_data`` that
        houses paths to individuals' photos. The photos must be of a type that Pillow
        supports (e.g., PNG, JPG). Paths can be relative or absolute.
    :type photo_path_col: str
    :param path_to_default_photo: The path to the photo to use if an individual does not
        have a photo path listed ``people_data``. This default photo will also be used
        if there is indeed a photo path specified but the photo cannot be found at that
        location. The photo must be of a type that Pillow supports (e.g., PNG, JPG). If
        specifying this argument using a single-backlash separator, make sure to use a
        raw string.
    :type path_to_default_photo: str
    :param path_to_output_dir: The path to the output directory to use. The output
        directory will store the final PDF, its constituent pages/Matplob figures, and
        the log file. If it does not exist, it will be created at runtime. If specifying
        this argument using a single-backlash separator, make sure to use a raw string.,
        defaults to 'intro_cards_output'
    :type path_to_output_dir: str, optional
    :param layout: Layout and formatting parameters controlling figure size, name and
        description placement, font sizes, and photo bounds. See :class:`CardLayout` for
        all options and defaults., defaults to CardLayout()
    :type layout: CardLayout, optional
    :raises OSError: If the default photo does not exist at the specified path, or if
        the default photo cannot be read by PIL, or if the specified output directory
        does not exist and then cannot be created
    :raises ValueError: If ``first_name_col``, ``last_name_col``, or ``photo_path_col``
        cannot be found in ``people_data``
    :return: Metadata pertaining to the number of intro cards that were created, the
        number of people for whom cards needed to be generated, and the names of people
        whose photos could not be found or read
    :rtype: StatsDict
    """
    _validate_inputs(
        people_data, first_name_col, last_name_col, photo_path_col, path_to_default_photo
    )

    if not os.path.exists(path_to_output_dir):
        try:
            os.makedirs(path_to_output_dir)
        except OSError:
            raise OSError(f"Failed to create `{path_to_output_dir}` directory.")

    logger_stream_handler = logging.StreamHandler()
    logger_stream_formatter = logging.Formatter("%(message)s")
    logger_stream_handler.setFormatter(logger_stream_formatter)
    logger.addHandler(logger_stream_handler)

    local_timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    logger_file_handler = logging.FileHandler(
        os.path.join(path_to_output_dir, f"names_{local_timestamp}.log"), mode="w"
    )
    logger_file_formatter = logging.Formatter("%(message)s")
    logger_file_handler.setFormatter(logger_file_formatter)
    logger.addHandler(logger_file_handler)

    stats: StatsDict = {
        "number_of_cards_created": 0,
        "number_of_cards_to_create": people_data.shape[0],
        "people_with_photo_warnings": [],
    }

    try:
        _make_figs(
            people_data,
            first_name_col,
            last_name_col,
            photo_path_col,
            path_to_default_photo,
            path_to_output_dir,
            layout,
            stats=stats,
        )
        figure_image_paths = glob.glob(os.path.join(path_to_output_dir, "*.png"))
        def _figure_sort_key(path: str) -> int:
            match = re.search(r"figure(\d+)\.png", path)
            assert match is not None, f"Unexpected filename format: {path}"
            return int(match.group(1))

        sorted_figure_image_paths = sorted(figure_image_paths, key=_figure_sort_key)
        first_img = Image.open(sorted_figure_image_paths[0])
        first_img.save(
            os.path.join(path_to_output_dir, "intro_cards.pdf"),
            resolution=_PDF_RESOLUTION,
            save_all=True,
            append_images=(Image.open(path) for path in sorted_figure_image_paths[1:]),
        )

        logger.info(
            f"\n\nComplete! See the directory `{path_to_output_dir}` for the PDF.\n"
        )
        if stats["people_with_photo_warnings"]:
            logger.info(
                "WARNING: Photos could not be found or read at the specified paths "
                "for the name(s) below. Please confirm the path(s) are valid and that "
                "the photo(s) are of a format supported by PIL.\n"
            )
            logger.info("\n".join(stats["people_with_photo_warnings"]))
        return stats
    except Exception as e:
        logger.error(e)
        raise
    finally:
        logger.removeHandler(logger_stream_handler)
        logger_file_handler.close()
        logger.removeHandler(logger_file_handler)


def make_pdf_preview(
    people_data: pd.DataFrame,
    first_name_col: str,
    last_name_col: str,
    photo_path_col: str,
    path_to_default_photo: str,
    layout: CardLayout = CardLayout(),
) -> StatsDict:
    """Show a preview in a Jupyter environment of the first page of the PDF that would
    be created if :func:`make_pdf` were run, and print log output to the console.

    This function is helpful to gauge how the output will look in response to tweaking
    certain parameters (e.g., ``name_font_size``) without having to actually iterate
    through the entirety of ``people_data`` and compile the PDF. Its parameters,
    defaults, and return type are identical to those of :func:`make_pdf`, except for its
    omission of ``path_to_output_dir``. It serves primarily as a wrapper for
    :func:`_make_fig_preview` to allow for more consistent naming in the public API.

    Because this function uses Matplotlib's inline backend, it is required to be run in
    a Jupyter environment. The figures displayed by this backend ultimately match those
    that are rendered by the Agg backend that is implicitly used in each of
    :func:`make_pdf`'s :func:`fig.savefig` calls.

    :param people_data: The pandas DataFrame containing all the data from which to make
        intro cards. Rows represent individuals, while columns represent attributes of
        those individuals. The choice of attributes is completely up to the user (e.g.,
        "Hometown", "Fun Fact"), but it is required that there be columns for first
        name, last name, and paths to individuals' photos (which will ultimately be
        displayed on their respective intro cards). The name of each column—except the
        ones for first name, last name, and photo paths—will ultimately end up being
        listed on individuals' intro cards in bold. The order of these columns dictates
        the order in which "column name: attribute value" pairings are displayed on the
        cards.
    :type people_data: pd.DataFrame
    :param first_name_col: The name of the column (Series) in ``people_data`` that
        houses first names
    :type first_name_col: str
    :param last_name_col: The name of the column (Series) in ``people_data`` that houses
        last names
    :type last_name_col: str
    :param photo_path_col: The name of the column (Series) in ``people_data`` that
        houses paths to individuals' photos. The photos must be of a type that Pillow
        supports (e.g., PNG, JPG). Paths can be relative or absolute.
    :type photo_path_col: str
    :param path_to_default_photo: The path to the photo to use if an individual does not
        have a photo path listed ``people_data``. This default photo will also be used
        if there is indeed a photo path specified but the photo cannot be found at that
        location. The photo must be of a type that Pillow supports (e.g., PNG, JPG). If
        specifying this argument using a single-backlash separator, make sure to use a
        raw string.
    :type path_to_default_photo: str
    :param layout: Layout and formatting parameters controlling figure size, name and
        description placement, font sizes, and photo bounds. See :class:`CardLayout` for
        all options and defaults., defaults to CardLayout()
    :type layout: CardLayout, optional
    :raises OSError: If the default photo does not exist at the specified path, or if
        the default photo cannot be read by PIL
    :raises ValueError: If ``first_name_col``, ``last_name_col``, or ``photo_path_col``
        cannot be found in ``people_data``
    :return: Metadata pertaining to the number of intro cards that were created, the
        number of people for whom cards needed to be generated, and the names of people
        whose photos could not be found or read
    :rtype: StatsDict
    """
    _validate_inputs(
        people_data, first_name_col, last_name_col, photo_path_col, path_to_default_photo
    )

    logger_stream_handler = logging.StreamHandler()
    logger_stream_formatter = logging.Formatter("%(message)s")
    logger_stream_handler.setFormatter(logger_stream_formatter)
    logger.addHandler(logger_stream_handler)

    stats: StatsDict = {
        "number_of_cards_created": 0,
        "number_of_cards_to_create": min(people_data.shape[0], 4),
        "people_with_photo_warnings": [],
    }

    try:
        _make_fig_preview(
            people_data,
            first_name_col,
            last_name_col,
            photo_path_col,
            path_to_default_photo,
            layout,
            stats=stats,
        )

        if stats["people_with_photo_warnings"]:
            logger.info(
                "WARNING: Photos could not be found at the specified paths "
                "for the name(s) below. Please confirm the photo path(s).\n"
            )
            logger.info("\n".join(stats["people_with_photo_warnings"]))
        return stats
    except Exception as e:
        logger.error(e)
        raise
    finally:
        logger.removeHandler(logger_stream_handler)


def _validate_inputs(
    people_data: pd.DataFrame,
    first_name_col: str,
    last_name_col: str,
    photo_path_col: str,
    path_to_default_photo: str,
) -> None:
    """Validate inputs shared by :func:`make_pdf` and :func:`make_pdf_preview`. Private
    function.

    Checks that the default photo exists and is readable by PIL, and that all required
    columns are present in ``people_data``.

    :param people_data: The pandas DataFrame containing all the data from which to make
        intro cards
    :type people_data: pd.DataFrame
    :param first_name_col: The name of the column (Series) in ``people_data`` that
        houses first names
    :type first_name_col: str
    :param last_name_col: The name of the column (Series) in ``people_data`` that houses
        last names
    :type last_name_col: str
    :param photo_path_col: The name of the column (Series) in ``people_data`` that
        houses paths to individuals' photos
    :type photo_path_col: str
    :param path_to_default_photo: The path to the default photo to validate
    :type path_to_default_photo: str
    :raises OSError: If the default photo does not exist at the specified path or cannot
        be read by PIL
    :raises ValueError: If ``first_name_col``, ``last_name_col``, or ``photo_path_col``
        cannot be found in ``people_data``
    :return: None
    :rtype: NoneType
    """
    if not os.path.exists(path_to_default_photo):
        raise OSError(
            "No photo exists at the specified default photo path. "
            "Please specify a valid path."
        )

    try:
        img = Image.open(path_to_default_photo)
        img.close()
    except OSError:
        raise OSError(
            f"Could not read the default photo at `{path_to_default_photo}`. "
            "Make sure the photo is of a format supported by PIL."
        )

    missing_columns = [
        col
        for col in [first_name_col, last_name_col, photo_path_col]
        if col not in people_data.columns
    ]
    if missing_columns:
        raise ValueError(
            "The following columns are not in `people_data`: "
            f"{', '.join(missing_columns)}. Please specify valid column names."
        )


def _make_page_fig(
    batch: pd.DataFrame,
    first_name_col: str,
    last_name_col: str,
    photo_path_col: str,
    path_to_default_photo: str,
    layout: CardLayout,
    dpi: int,
    stats: StatsDict,
) -> mpl.figure.Figure:
    """Create and populate a single page figure with up to ``_CARDS_PER_PAGE`` intro
    cards. Private function.

    :param batch: A slice of the processed ``people_data`` DataFrame containing up to
        ``_CARDS_PER_PAGE`` rows to render on this page
    :type batch: pd.DataFrame
    :param first_name_col: The name of the column (Series) in ``people_data`` that
        houses first names
    :type first_name_col: str
    :param last_name_col: The name of the column (Series) in ``people_data`` that houses
        last names
    :type last_name_col: str
    :param photo_path_col: The name of the column (Series) in ``people_data`` that
        houses paths to individuals' photos
    :type photo_path_col: str
    :param path_to_default_photo: The path to the photo to use if an individual does not
        have a photo path listed or the photo cannot be read
    :type path_to_default_photo: str
    :param layout: Layout and formatting parameters for the cards
    :type layout: CardLayout
    :param dpi: Resolution in dots per inch for the figure
    :type dpi: int
    :param stats: Metadata pertaining to the number of intro cards that were created,
        the number of people for whom cards needed to be generated, and the names of
        people whose photos could not be found or read
    :type stats: StatsDict
    :return: The populated Matplotlib figure for this page
    :rtype: mpl.figure.Figure
    """
    fig, axs = plt.subplots(2, 2, figsize=layout.figure_size, dpi=dpi)
    fig.tight_layout(h_pad=0.1, w_pad=0.1)
    for ax in axs.ravel():
        ax.axis("off")
    for row, ax in zip(batch.iterrows(), axs.ravel()):
        _make_card(
            row[1],
            ax,
            first_name_col,
            last_name_col,
            photo_path_col,
            path_to_default_photo,
            layout,
            stats=stats,
        )
    return fig


def _make_figs(
    people_data: pd.DataFrame,
    first_name_col: str,
    last_name_col: str,
    photo_path_col: str,
    path_to_default_photo: str,
    path_to_output_dir: str,
    layout: CardLayout,
    stats: StatsDict,
) -> None:
    """Iteratively grab batches of four rows (individuals) from ``people_data``, and for
    each batch save a Matplotlib figure that shows those four individuals' intro cards.
    Private function.

    All figures will be saved as PNG files in ``path_to_output_dir``. If the number of
    rows in ``people_data`` is not divisible by 4, the last figure will show only as
    many individuals are needed to account for every individual in the DataFrame.

    :param people_data: The pandas DataFrame containing all the data from which to make
        intro cards. Rows represent individuals, while columns represent attributes of
        those individuals. The choice of attributes is completely up to the user (e.g.,
        "Hometown", "Fun Fact"), but it is required that there be columns for first
        name, last name, and paths to individuals' photos (which will ultimately be
        displayed on their respective intro cards). The name of each column—except the
        ones for first name, last name, and photo paths—will ultimately end up being
        listed on individuals' intro cards in bold. The order of these columns dictates
        the order in which "column name: attribute value" pairings are displayed on the
        cards.
    :type people_data: pd.DataFrame
    :param first_name_col: The name of the column (Series) in ``people_data`` that
        houses first names
    :type first_name_col: str
    :param last_name_col: The name of the column (Series) in ``people_data`` that houses
        last names
    :type last_name_col: str
    :param photo_path_col: The name of the column (Series) in ``people_data`` that
        houses paths to individuals' photos. The photos must be of a type that Pillow
        supports (e.g., PNG, JPG). Paths can be relative or absolute.
    :type photo_path_col: str
    :param path_to_default_photo: The path to the photo to use if an individual does not
        have a photo path listed ``people_data``. This default photo will also be used
        if there is indeed a photo path specified but the photo cannot be found at that
        location. The photo must be of a type that Pillow supports (e.g., PNG, JPG). If
        specifying this argument using a single-backlash separator, make sure to use a
        raw string.
    :type path_to_default_photo: str
    :param path_to_output_dir: The path to the output directory to use. The output
        directory will store the final PDF, its constituent pages/Matplob figures, and
        the log file. If it does not exist, it will be created at runtime. If specifying
        this argument using a single-backlash separator, make sure to use a raw string.
    :type path_to_output_dir: str
    :param layout: Layout and formatting parameters for the cards
    :type layout: CardLayout
    :param stats: Metadata pertaining to the number of intro cards that were created,
        the number of people for whom cards needed to be generated, and the names of
        people whose photos could not be found or read
    :type stats: StatsDict
    :return: None
    :rtype: NoneType
    """
    people_data = _format_data_and_derive_full_names(
        people_data, first_name_col, last_name_col, photo_path_col
    )

    with mpl.rc_context({"mathtext.default": "bf"}):
        for i, start in enumerate(range(0, len(people_data), _CARDS_PER_PAGE), start=1):
            batch = people_data.iloc[start : start + _CARDS_PER_PAGE]
            fig = _make_page_fig(
                batch,
                first_name_col,
                last_name_col,
                photo_path_col,
                path_to_default_photo,
                layout,
                dpi=_SAVEFIG_DPI,
                stats=stats,
            )
            fig.savefig(os.path.join(path_to_output_dir, f"figure{i}.png"))
            plt.close(fig)


def _make_fig_preview(
    people_data: pd.DataFrame,
    first_name_col: str,
    last_name_col: str,
    photo_path_col: str,
    path_to_default_photo: str,
    layout: CardLayout,
    stats: StatsDict,
) -> None:
    """Show a preview (using :func:`plt.show`) of the first page of the PDF that would
    be created if :func:`make_pdf` were run. Private function.

    This function is called internally by ``make_pdf_preview`` to gauge how the output
    will look in response to tweaking certain parameters (e.g., ``name_font_size``),
    without having to iterate through the entirety of ``people_data``. Its parameters
    are identical to those of :func:`_make_figs`, except for its omission of
    ``path_to_output_dir``.

    :param people_data: The pandas DataFrame containing all the data from which to make
        intro cards. Rows represent individuals, while columns represent attributes of
        those individuals. The choice of attributes is completely up to the user (e.g.,
        "Hometown", "Fun Fact"), but it is required that there be columns for first
        name, last name, and paths to individuals' photos (which will ultimately be
        displayed on their respective intro cards). The name of each column—except the
        ones for first name, last name, and photo paths—will ultimately end up being
        listed on individuals' intro cards in bold. The order of these columns dictates
        the order in which "column name: attribute value" pairings are displayed on the
        cards.
    :type people_data: pd.DataFrame
    :param first_name_col: The name of the column (Series) in ``people_data`` that
        houses first names
    :type first_name_col: str
    :param last_name_col: The name of the column (Series) in ``people_data`` that houses
        last names
    :type last_name_col: str
    :param photo_path_col: The name of the column (Series) in ``people_data`` that
        houses paths to individuals' photos. The photos must be of a type that Pillow
        supports (e.g., PNG, JPG). Paths can be relative or absolute.
    :type photo_path_col: str
    :param path_to_default_photo: The path to the photo to use if an individual does not
        have a photo path listed ``people_data``. This default photo will also be used
        if there is indeed a photo path specified but the photo cannot be found at that
        location. The photo must be of a type that Pillow supports (e.g., PNG, JPG). If
        specifying this argument using a single-backlash separator, make sure to use a
        raw string.
    :type path_to_default_photo: str
    :param layout: Layout and formatting parameters for the cards
    :type layout: CardLayout
    :param stats: Metadata pertaining to the number of intro cards that were created,
        the number of people for whom cards needed to be generated, and the names of
        people whose photos could not be found or read
    :type stats: StatsDict
    :return: None
    :rtype: NoneType
    """
    people_data = _format_data_and_derive_full_names(
        people_data, first_name_col, last_name_col, photo_path_col
    )

    plt.close("all")

    with mpl.rc_context({"mathtext.default": "bf"}):
        batch = people_data.iloc[0:_CARDS_PER_PAGE]
        # dpi controls the resolution of figure preview in interactive environment
        fig = _make_page_fig(
            batch,
            first_name_col,
            last_name_col,
            photo_path_col,
            path_to_default_photo,
            layout,
            dpi=_PREVIEW_DPI,
            stats=stats,
        )
        plt.show()  # Needs to be called explicitly to properly render Mathtext in bold
        plt.close(fig)


def _make_card(
    row: pd.Series,
    ax: axes.Axes,
    first_name_col: str,
    last_name_col: str,
    photo_path_col: str,
    path_to_default_photo: str,
    layout: CardLayout,
    stats: StatsDict,
) -> None:
    """Create a single intro card by plotting an individual's name, photo, and
    description on a Matplotlib Axes. Private function.

    :param row: The row in ``people_data`` from which to create the intro card. Each row
        represents an individual.
    :type row: pd.Series
    :param ax: The Matplotlib Axes object on which to plot the individual's name, photo,
        and description string
    :type ax: mpl.axes.Axes
    :param first_name_col: The name of the column (Series) in ``people_data`` that
        houses first names
    :type first_name_col: str
    :param last_name_col: The name of the column (Series) in ``people_data`` that houses
        last names
    :type last_name_col: str
    :param photo_path_col: The name of the column (Series) in ``people_data`` that
        houses paths to individuals' photos. The photos must be of a type that Pillow
        supports (e.g., PNG, JPG). Paths can be relative or absolute.
    :type photo_path_col: str
    :param path_to_default_photo: The path to the photo to use if an individual does not
        have a photo path listed ``people_data``. This default photo will also be used
        if there is indeed a photo path specified but the photo cannot be found at that
        location. The photo must be of a type that Pillow supports (e.g., PNG, JPG). If
        specifying this argument using a single-backlash separator, make sure to use a
        raw string.
    :type path_to_default_photo: str
    :param layout: Layout and formatting parameters for the card
    :type layout: CardLayout
    :param stats: Metadata pertaining to the number of intro cards that were created,
        the number of people for whom cards needed to be generated, and the names of
        people whose photos could not be found or read
    :type stats: StatsDict
    :return: None
    :rtype: NoneType
    """
    ax.axis("on")
    ax.patch.set_edgecolor("black")
    ax.xaxis.set_visible(False)
    ax.yaxis.set_visible(False)

    name_right_padding = 0.02  # Padding on right edge of figure for _WrapText
    # Plot name
    name_text = _WrapText(
        layout.name_x_coord,
        layout.name_y_coord,
        row["Full Name"],
        fontsize=layout.name_font_size,
        width=1 - layout.name_x_coord - name_right_padding,
        widthcoords=ax.transAxes,
        transform=ax.transAxes,
        fontweight="bold",
        va="top",
        ha="left",
    )
    ax.add_artist(name_text)

    name_text_bbox = name_text.get_window_extent()  # In display coordinates
    name_text_bbox_ax_coords = name_text_bbox.transformed(ax.transAxes.inverted())
    desc_y1_coord = name_text_bbox_ax_coords.y0 - layout.desc_padding

    # Plot the description
    # If the provided font size would cause its bottom boundary to come within 0.02
    # of the bottom of the card or exceed the bottom of the card (and therefore be
    # cut off), iteratively reduce the font size by 5% until this is no longer the case.
    desc_font_size = layout.desc_font_size
    while True:
        desc_text = _WrapText(
            layout.name_x_coord,
            desc_y1_coord,
            _get_description_string_from_row(
                row, first_name_col, last_name_col, photo_path_col
            ),
            fontsize=desc_font_size,
            width=1 - layout.name_x_coord - name_right_padding,
            widthcoords=ax.transAxes,
            transform=ax.transAxes,
            va="top",
            linespacing=1.67,
        )
        ax.add_artist(desc_text)
        desc_text_bbox = desc_text.get_window_extent()  # In display coordinates
        desc_text_bbox_ax_coords = desc_text_bbox.transformed(ax.transAxes.inverted())
        if desc_text_bbox_ax_coords.y0 >= _BOTTOM_MARGIN:
            break
        else:
            desc_text.remove()
            desc_font_size = desc_font_size * _FONT_SHRINK_FACTOR

    if row[photo_path_col] != "":
        if not os.path.exists(row[photo_path_col]):
            person_status = "WARNING"
            person_status_msg = "Photo path provided but photo not found; default used"
            stats["people_with_photo_warnings"].append(row["Full Name"])
            img = Image.open(path_to_default_photo)
        else:
            try:
                img = Image.open(row[photo_path_col])
                person_status = "SUCCESS"
                person_status_msg = "Photo path provided and photo read"
            except OSError:
                img = Image.open(path_to_default_photo)
                person_status = "WARNING"
                person_status_msg = (
                    f"Could not read photo at `{row[photo_path_col]}`; default used"
                )
                stats["people_with_photo_warnings"].append(row["Full Name"])
    else:
        img = Image.open(path_to_default_photo)
        person_status = "SUCCESS"
        person_status_msg = "No photo path provided"

    ax_inset = ax.inset_axes(layout.photo_axes_bounds, anchor="NW")
    ax_inset.imshow(img)
    img.close()
    ax_inset.tick_params(axis="both", which="both", length=0)
    ax_inset.set_xticks([])
    ax_inset.set_yticks([])
    for spine in ax_inset.spines.values():
        spine.set_visible(True)
        spine.set_color("black")
        spine.set_linewidth(0.1)

    current_progress_for_log_message = (
        f"[{stats['number_of_cards_created'] + 1}/{stats['number_of_cards_to_create']}]"
    )
    person_log_message = (
        f"{current_progress_for_log_message} {person_status} "
        f": {row['Full Name']} - {person_status_msg}"
    )
    logger.info(person_log_message)
    stats["number_of_cards_created"] += 1


def _get_description_string_from_row(
    row: pd.Series, first_name_col: str, last_name_col: str, photo_path_col: str
) -> str:
    """Return a string that, for a given row/individual, lists all their "column name:
    attribute value" pairings for each column in ``people_data`` (except columns related
    to names or photo path). Private function.

    Each "column name: attribute value" pairing is separated by a new line, and each
    "column name" is bolded (by wrapping it in appropriate Mathtext characters). Text on
    any given line is wrapped, such that it approaches—but does not touch—the right
    border of the card. If an individual's "attribute value" is left blank, then that
    particular "column name: attribute value" pairing will be omitted from the
    description string.

    :param row: The row in ``people_data`` to describe. Each row represents an
        individual.
    :type row: pd.Series
    :param first_name_col: The name of the column (Series) in ``people_data`` that
        houses first names
    :type first_name_col: str
    :param last_name_col: The name of the column (Series) in ``people_data`` that houses
        last names
    :type last_name_col: str
    :param photo_path_col: The name of the column (Series) in ``people_data`` that
        houses photo paths. Paths can be relative or absolute.
    :type photo_path_col: str
    :return: A formatted description string listing all the appropriate "column name:
        attribute value" pairings of `row`
    :rtype: str
    """
    name_and_photo_cols = ["Full Name", first_name_col, last_name_col, photo_path_col]
    row_attributes_ex_names_and_photo = row.drop(name_and_photo_cols)

    desc_string_components = [
        f"${column_name}:$ {attribute_value}"
        for column_name, attribute_value in row_attributes_ex_names_and_photo.items()
        if attribute_value != ""
    ]

    return "\n".join(desc_string_components)


class _WrapText(Text):
    r"""Extend the functionality of :class:`matplotlib.text.Text` by allowing for text to
    be wrapped when a line reaches a certain width (in effect forming a text box).
    Private class.

    With this class, the user can specify the maximum width—in units of
    ``widthcoords``—of a Matplotlib :class:`Text` instance. If the addition of any
    character or word to a line would bring the length of that line beyond the maximum
    width, a new line will be inserted and that character or word will start the new
    line. The class does this by inhering from :class:`matplotlib.text.Text` and
    overriding its :meth:`_get_wrap_line_width` method, ultimately creating a new
    :class:`matplotlib.text.Text` artist. Besides ``width`` and ``widthcoords``, all
    arguments passed when instantiating this class (including ``kwargs``) are passed to
    :class:`matplotlib.text.Text`.

    (This implementation comes from a Github Gist posted by user "dneuman".
    `Link to Gist <https://gist.github.com/dneuman/90af7551c258733954e3b1d1c17698fe>`_.)

    :param x: The x-coordinate of the text. All subsequent code in this module converts
        this number to an Axes-relative coordinate (instead of the default transData) by
        passing ``transform=ax.transAxes`` to the constructor., defaults to 0
    :type x: float, optional
    :param y: The y-coordinate of the text. All subsequent code in this module converts
        this number to an Axes-relative coordinate (instead of the default transData) by
        passing ``transform=ax.transAxes`` to the constructor., defaults to 0
    :type y: float, optional
    :param text: The text string to display, defaults to ""
    :type text: str, optional
    :param width: The maximum allowable width of the text to be displayed. Beyond this
        maximum width, the text is wrapped and a new line is started., defaults to 0
    :type width: float, optional
    :param widthcoords: The coordinate system of ``width``, defaults to None (which is
        interpreted downstream in units of screen pixels)
    :type widthcoords: :class:`mpl.transforms.Transform` or None, optional
    """

    def __init__(
        self,
        x: float = 0,
        y: float = 0,
        text: str = "",
        width: float = 0,
        widthcoords: Transform | None = None,
        **kwargs,
    ) -> None:
        r"""Initialize an instance of :class:`_WrapText` at coordinates ``x``, ``y`` with
        string ``text``, with a maximum width of ``width`` expressed in units of
        ``widthcoords``.

        Besides ``width`` and ``widthcoords``, all arguments (including ``kwargs``) of
        this class are passed to :class:`matplotlib.text.Text`.

        :param x: The x-coordinate of the text. All subsequent code in this module
            converts this number to an Axes-relative coordinate (instead of the default
            transData) by passing ``transform=ax.transAxes`` to the constructor.,
            defaults to 0
        :type x: float, optional
        :param y: The y-coordinate of the text. All subsequent code in this module
            converts this number to an Axes-relative coordinate (instead of the default
            transData) by passing ``transform=ax.transAxes`` to the constructor.,
            defaults to 0
        :type y: float, optional
        :param text: The text string to display, defaults to ""
        :type text: str, optional
        :param width: The maximum allowable width of the text to be displayed. Beyond
            this maximum width, the text is wrapped and a new line is started., defaults
            to 0
        :type width: float, optional
        :param widthcoords: The coordinate system of ``width``, defaults to None (which
            is interpreted downstream in units of screen pixels)
        :type widthcoords: :class:`matplotlib.transforms.Transform` or None, optional
        :return: None
        :rtype: NoneType
        """
        Text.__init__(self, x=x, y=y, text=text, wrap=True, clip_on=True, **kwargs)
        if not widthcoords:
            self.width = width
        else:
            a = widthcoords.transform_point([(0, 0), (width, 0)])
            self.width = a[1][0] - a[0][0]

    def _get_wrap_line_width(self) -> float:
        """Return the maximum allowable width of the :class:`_WrapText` instance.
        Private method.

        This method overrides the one implemented by :class:`matplotlib.text.Text`,
        which is what allows the text to be wrapped.

        :return: The maximum allowable width of the :class:`_WrapText` instance, beyond
            which the text is wrapped.
        :rtype: float
        """
        return self.width


def _format_data_and_derive_full_names(
    df: pd.DataFrame, first_name_col: str, last_name_col: str, photo_path_col: str
) -> pd.DataFrame:
    r"""Format DataFrame for Mathtext compatibility and create Full Name column. Private
    function.

    This function replaces null values with empty strings, converts all values to
    strings, and trims whitespace. It also creates a "Full Name" column by combining the
    first and last name columns. Custom columns are formatted for Mathtext compatibility
    by removing forbidden characters (``~``, ``^``, ``\``) from column names, escaping
    special Mathtext characters (space, ``#``, ``$``, ``%``, ``_``, ``{``, ``}``) in
    column names, and escaping dollar signs (``$``) in column values. Name-related and
    photo path columns retain their original column names.

    :param df: DataFrame to process, containing individual records with their attributes
    :type df: pd.DataFrame
    :param first_name_col: Name of the column containing first names
    :type first_name_col: str
    :param last_name_col: Name of the column containing last names
    :type last_name_col: str
    :param photo_path_col: Name of the column containing photo file paths
    :type photo_path_col: str
    :return: Processed DataFrame with Mathtext-compatible formatting and Full Name
        column
    :rtype: pd.DataFrame
    """
    df = df.fillna("").astype(str).apply(lambda x: x.str.strip())

    df["Full Name"] = df[first_name_col].str.cat(df[last_name_col], sep=" ").str.strip()

    name_and_photo_cols = ["Full Name", first_name_col, last_name_col, photo_path_col]

    # Format custom columns for Mathtext
    forbidden_chars_in_col_names = ["~", "^", "\\"]
    prepend_with_backslash_in_col_names = [" ", "#", "$", "%", "_", "{", "}"]

    new_columns = {}
    for col in df.columns:
        if col not in name_and_photo_cols:
            # Prepend backslash to any dollar signs in the values
            df[col] = df[col].str.replace("$", r"\$")
            # Derive formatted column names
            formatted_col = col.strip()
            for char in forbidden_chars_in_col_names:
                formatted_col = formatted_col.replace(char, "")
            for char in prepend_with_backslash_in_col_names:
                formatted_col = formatted_col.replace(char, rf"\{char}")
            new_columns[col] = formatted_col
        else:
            new_columns[col] = col

    df = df.rename(columns=new_columns)
    return df
