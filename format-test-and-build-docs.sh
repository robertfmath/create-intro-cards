#!/bin/sh

# This script automates the process of formatting and linting the Python code (using Ruff),
# formatting docstrings (using docformatter), running tests, and locally building the project's
# documentation (using Sphinx). The GitHub Actions workflow expects formatting to have already been applied
# and tests to have passed, so this is useful to run before pushing or creating a pull request.

# Run Ruff formatting
echo "Running Ruff format on create_intro_cards.py"
uv run ruff format create_intro_cards.py
echo "Running Ruff format on tests/test_create_intro_cards.py"
uv run ruff format tests/test_create_intro_cards.py

if [ $? -ne 0 ]; then
    echo "Ruff formatting failed."
    exit 1
fi

# Run Ruff linting
echo "Running Ruff lint on create_intro_cards.py"
uv run ruff check create_intro_cards.py
echo "Running Ruff lint on tests/test_create_intro_cards.py"
uv run ruff check tests/test_create_intro_cards.py

if [ $? -ne 0 ]; then
    echo "Ruff linting failed."
    exit 1
fi

# Run docformatter to format docstrings (wrapping at 88 characters, in line with Black)
echo "Running docformatter on create_intro_cards.py"
uv run docformatter --in-place create_intro_cards.py
echo "Running docformatter on tests/test_create_intro_cards.py"
uv run docformatter --in-place tests/test_create_intro_cards.py

if [ $? -ne 0 ]; then
    echo "Docformatter failed."
    exit 1
fi

# Run tests
echo "Running tests"
uv run python -m unittest tests/test_create_intro_cards.py
if [ $? -ne 0 ]; then
    echo "Tests failed."
    exit 1
fi

# Build documentation with Sphinx
cd ./docs

echo "Building documentation with Sphinx"
if [ "$(uname)" = "Darwin" ] || [ "$(uname)" = "Linux" ]; then
    uv run make clean && uv run make html
else
    uv run ./make.bat clean && uv run ./make.bat html
fi

if [ $? -ne 0 ]; then
    echo "Documentation build failed."
    exit 1
fi

cd ..

exit 0
