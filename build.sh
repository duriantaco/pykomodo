#!/bin/bash

if [ ! -f pyproject.toml ]; then
    echo "Error: pyproject.toml not found. Please run this script from the project root directory."
    exit 1
fi

echo "Cleaning up previous builds..."
rm -rf dist build

echo "Building the package..."
python3 -m build
if [ $? -ne 0 ]; then
    echo "Error: Build failed."
    exit 1
fi

echo "Uploading to PyPI..."
twine upload dist/*
if [ $? -ne 0 ]; then
    echo "Error: Upload failed."
    exit 1
fi

echo "Done."