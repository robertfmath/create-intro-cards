from datetime import datetime
import os
import shutil
import unittest
from unittest.mock import patch

import pandas as pd
from pypdf import PdfReader

import create_intro_cards


class TestMakePDF(unittest.TestCase):
    """Test the `make_pdf` function of create_intro_cards."""

    delete_output = True

    @classmethod
    def setUpClass(cls):
        tests_dir = os.path.dirname(__file__)
        cls.people_data = pd.read_csv(os.path.join(tests_dir, "test_people_data.csv"))
        cls.path_to_default_photo = os.path.join(
            tests_dir, "test_photos", "test_default_photo.jpg"
        )
        cls.path_to_output_dir = os.path.join(tests_dir, "test_output")

        cls.patcher = patch("create_intro_cards.datetime")
        cls.mock_datetime = cls.patcher.start()
        cls.fake_now = datetime(2025, 3, 12, 10, 24, 16)
        cls.mock_datetime.now.return_value = cls.fake_now

        cls.timestamp_str = cls.fake_now.strftime("%Y%m%dT%H%M%S")
        cls.path_to_log_file = os.path.join(
            cls.path_to_output_dir, f"names_{cls.timestamp_str}.log"
        )

        cls.stats = create_intro_cards.make_pdf(
            cls.people_data,
            "First Name",
            "Last Name",
            "Photo Path",
            cls.path_to_default_photo,
            cls.path_to_output_dir,
        )

    @classmethod
    def tearDownClass(cls):
        if cls.delete_output:
            shutil.rmtree(cls.path_to_output_dir)
        cls.patcher.stop()

    def test_pdf_file_created(self):
        self.assertTrue(
            os.path.exists(os.path.join(self.path_to_output_dir, "./intro_cards.pdf"))
        )

    def test_log_file_created(self):
        self.assertTrue(os.path.exists(self.path_to_log_file))

    def test_every_person_has_card(self):
        self.assertEqual(
            self.stats["number_of_cards_created"], self.people_data.shape[0]
        )

    def test_num_warnings(self):
        self.assertEqual(len(self.stats["people_with_photo_warnings"]), 2)

    def test_pdf_has_correct_number_of_pages(self):
        reader = PdfReader(os.path.join(self.path_to_output_dir, "./intro_cards.pdf"))
        actual_pages_in_pdf = len(reader.pages)

        cards_per_page = 4
        expected_pages_in_pdf = (
            self.people_data.shape[0] + cards_per_page - 1
        ) // cards_per_page

        self.assertEqual(actual_pages_in_pdf, expected_pages_in_pdf)

    def test_log_file_contents(self):
        expected_photo_read_msg = (
            "SUCCESS : First4 Last4 - Photo path provided and photo read"
        )
        expected_photo_not_found_warning = (
            "WARNING : First5First5 Last5 - Photo path provided but photo not found; "
            "default used"
        )
        expected_unreadable_photo_warning = (
            "WARNING : First6 Last6Last6 - Could not read photo at "
            "`tests/test_photos/test_unreadable_photo.txt`; default used"
        )
        expected_no_photo_path_provided_msg = (
            "SUCCESS : First7First7 Last7Last7 - No photo path provided"
        )
        expected_end_warning = (
            "\nWARNING: Photos could not be found or read at the specified paths "
            "for the name(s) below. Please confirm the path(s) are valid and that "
            "the photo(s) are of a format supported by PIL.\n\nFirst5First5 Last5"
            "\nFirst6 Last6Last6"
        )
        with open(self.path_to_log_file, "r") as log_file:
            log_file_contents = log_file.read()
        self.assertIn(expected_photo_read_msg, log_file_contents)
        self.assertIn(expected_photo_not_found_warning, log_file_contents)
        self.assertIn(expected_unreadable_photo_warning, log_file_contents)
        self.assertIn(expected_no_photo_path_provided_msg, log_file_contents)
        self.assertIn(expected_end_warning, log_file_contents)

    def test_oserror_default_photo_missing(self):
        with self.assertRaises(OSError) as context:
            create_intro_cards.make_pdf(
                self.people_data,
                "First Name",
                "Last Name",
                "Photo Path",
                "./tests/test_photos/non_existent_photo.jpg",
                self.path_to_output_dir,
            )
        self.assertIn(
            "No photo exists at the specified default photo path",
            str(context.exception),
        )

    def test_oserror_default_photo_unreadable(self):
        with self.assertRaises(OSError) as context:
            create_intro_cards.make_pdf(
                self.people_data,
                "First Name",
                "Last Name",
                "Photo Path",
                "./tests/test_photos/test_unreadable_photo.txt",
                self.path_to_output_dir,
            )
        self.assertIn(
            (
                "Could not read the default photo at "
                "`./tests/test_photos/test_unreadable_photo.txt`"
            ),
            str(context.exception),
        )

    def test_valueerror_missing_columns(self):
        with self.assertRaises(ValueError) as context:
            create_intro_cards.make_pdf(
                self.people_data,
                "NonExistentFirstNameCol",
                "NonExistentLastNameCol",
                "NonExistentPhotoPathCol",
                self.path_to_default_photo,
                self.path_to_output_dir,
            )
        self.assertIn(
            (
                "The following columns are not in `people_data`: "
                "NonExistentFirstNameCol, NonExistentLastNameCol, "
                "NonExistentPhotoPathCol"
            ),
            str(context.exception),
        )


class TestMakePreviewPDF(unittest.TestCase):
    """Test the `make_pdf_preview` function of create_intro_cards."""

    @classmethod
    def setUpClass(cls):
        tests_dir = os.path.dirname(__file__)
        cls.people_data = pd.read_csv(os.path.join(tests_dir, "test_people_data.csv"))
        cls.path_to_default_photo = os.path.join(
            tests_dir, "test_photos", "test_default_photo.jpg"
        )

    def test_four_card_previews_made_if_more_than_three_people(self):
        stats = create_intro_cards.make_pdf_preview(
            self.people_data,
            "First Name",
            "Last Name",
            "Photo Path",
            self.path_to_default_photo,
        )
        self.assertEqual(stats["number_of_cards_created"], 4)

    def test_num_card_previews_if_less_than_four_people(self):
        number_of_people_to_include = 2
        stats = create_intro_cards.make_pdf_preview(
            self.people_data.copy().head(number_of_people_to_include),
            "First Name",
            "Last Name",
            "Photo Path",
            self.path_to_default_photo,
        )
        self.assertEqual(
            stats["number_of_cards_created"],
            number_of_people_to_include,
        )

    def test_oserror_default_photo_missing(self):
        with self.assertRaises(OSError) as context:
            create_intro_cards.make_pdf_preview(
                self.people_data,
                "First Name",
                "Last Name",
                "Photo Path",
                "./tests/test_photos/non_existent_photo.jpg",
            )
        self.assertIn(
            "No photo exists at the specified default photo path",
            str(context.exception),
        )

    def test_oserror_default_photo_unreadable(self):
        with self.assertRaises(OSError) as context:
            create_intro_cards.make_pdf_preview(
                self.people_data,
                "First Name",
                "Last Name",
                "Photo Path",
                "./tests/test_photos/test_unreadable_photo.txt",
            )
        self.assertIn(
            (
                "Could not read the default photo at "
                "`./tests/test_photos/test_unreadable_photo.txt`"
            ),
            str(context.exception),
        )

    def test_valueerror_missing_columns(self):
        with self.assertRaises(ValueError) as context:
            create_intro_cards.make_pdf_preview(
                self.people_data,
                "NonExistentFirstNameCol",
                "NonExistentLastNameCol",
                "NonExistentPhotoPathCol",
                self.path_to_default_photo,
            )
        self.assertIn(
            (
                "The following columns are not in `people_data`: "
                "NonExistentFirstNameCol, NonExistentLastNameCol, "
                "NonExistentPhotoPathCol"
            ),
            str(context.exception),
        )


class TestGetDescriptionStringFromRow(unittest.TestCase):
    """Test the `_get_description_string_from_row` function of create_intro_cards."""

    def test_blank_attribute_value_skipped(self):
        row_data = {
            "First Name": "First1",
            "Last Name": "Last1",
            "Full Name": "First1 Last1",
            "Photo Path": "path/to/photo.png",
            "Hometown": "",
        }
        row = pd.Series(row_data)
        expected_description_string = r""
        self.assertEqual(
            create_intro_cards._get_description_string_from_row(
                row, "First Name", "Last Name", "Photo Path"
            ),
            expected_description_string,
        )

    def test_entire_description_string(self):
        row_data = {
            "First Name": "First1",
            "Last Name": "Last1",
            "Full Name": "First1 Last1",
            "Photo Path": "path/to/photo.png",
            "Hometown": r"New York\$, NY",
            r"Birth\ Month": "March",
            r"Favorite\ Dessert": "",
            "Hobbies/Interests": r"Cooking,\ Baking",
            r"Fun\ Fact": r"I'm\ fluent\ in\ four\ languages",
        }
        row = pd.Series(row_data)
        expected_description_string = (
            r"$Hometown:$ New York\$, NY"
            + "\n"
            + r"$Birth\ Month:$ March"
            + "\n"
            + r"$Hobbies/Interests:$ Cooking,\ Baking"
            + "\n"
            + r"$Fun\ Fact:$ I'm\ fluent\ in\ four\ languages"
        )
        self.assertEqual(
            create_intro_cards._get_description_string_from_row(
                row, "First Name", "Last Name", "Photo Path"
            ),
            expected_description_string,
        )


class TestFormatDataAndDeriveFullNames(unittest.TestCase):
    """Test the `_format_data_and_derive_full_names` function."""

    def test_all_values_converted_to_strings_and_stripped(self):
        df = pd.DataFrame(
            {
                "First Name": [" John "],
                "Last Name": [" Doe "],
                "Photo Path": ["path.jpg"],
                "Age": [25],
                "Height": [" 6'0\" "],
            }
        )
        result = create_intro_cards._format_data_and_derive_full_names(
            df, "First Name", "Last Name", "Photo Path"
        )
        self.assertEqual(result.iloc[0]["First Name"], "John")
        self.assertEqual(result.iloc[0]["Age"], "25")
        self.assertEqual(result.iloc[0]["Height"], "6'0\"")

    def test_full_name_column_created(self):
        df = pd.DataFrame(
            {"First Name": ["John"], "Last Name": ["Doe"], "Photo Path": ["path.jpg"]}
        )
        result = create_intro_cards._format_data_and_derive_full_names(
            df, "First Name", "Last Name", "Photo Path"
        )
        self.assertEqual(result.iloc[0]["Full Name"], "John Doe")

    def test_dollar_signs_escaped_in_values_of_custom_columns(self):
        df = pd.DataFrame(
            {
                "First Name": ["John $"],
                "Last Name": ["Doe"],
                "Photo Path": ["path.jpg"],
                "Salary": ["$100,000"],
                "Notes": ["Earns $$$"],
            }
        )
        result = create_intro_cards._format_data_and_derive_full_names(
            df, "First Name", "Last Name", "Photo Path"
        )
        self.assertEqual(result.iloc[0]["Salary"], r"\$100,000")
        self.assertEqual(result.iloc[0]["Notes"], r"Earns \$\$\$")
        # Values in name/photo columns should not be escaped
        self.assertEqual(result.iloc[0]["First Name"], "John $")

    def test_whitespace_stripped_from_custom_column_names(self):
        df = pd.DataFrame(
            {
                " First Name ": ["John"],
                " Last Name ": ["Doe"],
                " Photo Path ": ["path.jpg"],
                " Hometown ": ["NYC"],
            }
        )
        result = create_intro_cards._format_data_and_derive_full_names(
            df, " First Name ", " Last Name ", " Photo Path "
        )
        self.assertIn("Hometown", result.columns)
        self.assertNotIn(" Hometown ", result.columns)
        # Whitespace should not be stripped from name/photo column names
        self.assertIn(" First Name ", result.columns)
        self.assertIn(" Photo Path ", result.columns)

    def test_mathtext_formatting_for_custom_column_names(self):
        df = pd.DataFrame(
            {
                " First Name": ["John"],
                "Last Name$": ["Doe"],
                "Photo_^Path": ["path.jpg"],
                "Hobby #1": ["Reading"],
                "Salary {($)}": ["100k"],
                "Height %": ["6'0\""],
                "Fun_Fact": ["Likes {math}"],
                "Notes~": ["Something"],
                "Skills^2": ["Coding"],
                "Intere\\sts": ["Cooking"],
            }
        )
        result = create_intro_cards._format_data_and_derive_full_names(
            df, " First Name", "Last Name$", "Photo_^Path"
        )
        # Check that special characters are properly escaped
        self.assertIn(r"Hobby\ \#1", result.columns)
        self.assertIn(r"Salary\ \{(\$)\}", result.columns)
        self.assertIn(r"Height\ \%", result.columns)
        self.assertIn(r"Fun\_Fact", result.columns)
        # Check that forbidden characters are removed
        self.assertIn("Notes", result.columns)
        self.assertIn("Skills2", result.columns)
        self.assertIn("Interests", result.columns)
        # Check that name/photo columns are unchanged
        self.assertIn(" First Name", result.columns)
        self.assertIn("Last Name$", result.columns)
        self.assertIn("Photo_^Path", result.columns)

    def test_values_in_name_and_photo_cols_preserved(self):
        df = pd.DataFrame(
            {
                "First Name": ["John$"],
                "Last Name": ["Doe#"],
                "Photo Path": ["path$.jpg"],
                "Other": ["test$"],
            }
        )
        result = create_intro_cards._format_data_and_derive_full_names(
            df, "First Name", "Last Name", "Photo Path"
        )
        # Name and photo columns should not be modified
        self.assertEqual(result.iloc[0]["First Name"], "John$")
        self.assertEqual(result.iloc[0]["Last Name"], "Doe#")
        self.assertEqual(result.iloc[0]["Photo Path"], "path$.jpg")
        # Other columns should be modified
        self.assertEqual(result.iloc[0]["Other"], r"test\$")


if __name__ == "__main__":
    unittest.main()
