#!/bin/bash

# Get the version argument from the command line
VERSION="$1"

if [ -z "$VERSION" ]; then
    echo "Usage: $0 <version>"
    exit 1
fi

# Loop through each folder in the 'integrations' directory
for folder in "$(pwd)"/integrations/*; do
    if [ -d "$folder" ]; then
        if [ ! -f "$folder"/pyproject.toml ]; then
            continue
        fi

        echo "Bumping integration $folder"

        echo "Run 'make install'"
        (cd "$folder" && make install)

        echo "Enter the Python virtual environment in the .venv folder"
        (cd "$folder" && source .venv/bin/activate)

        echo "Bump the version ocean version using Poetry"
        (cd "$folder" && poetry add port-ocean@$VERSION -E cli)

        echo "Run towncrier create"
        (cd "$folder" && towncrier create --content "Bumped ocean version to $VERSION" 1.improvement.md)

        echo "Run towncrier build"
        current_version=$(poetry version --short)

        echo "Current version: $current_version, updating patch version"
        IFS='.' read -ra version_components <<< "$current_version"
        major_version="${version_components[0]}"
        minor_version="${version_components[1]}"
        patch_version="${version_components[2]}"

        ((patch_version++))
        new_version="$major_version.$minor_version.$patch_version"
        echo "New version: $new_version"

        poetry version "$new_version"

        echo "New version: $NEW_VERSION"

        echo "Run towncrier build to increment the patcb version"
        (cd "$folder" && towncrier build --version $NEW_VERSION --yes)

        echo "Run 'make install' again"
        (cd "$folder" && make install)
        
        deactivate
    fi
done
