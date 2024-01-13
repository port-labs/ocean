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
        (cd "$folder" && source .venv/bin/activate && poetry add port-ocean@$VERSION -E cli --no-cache)

        echo "Run towncrier create"
        (cd "$folder" && source .venv/bin/activate && towncrier create --content "Bumped ocean version to $VERSION" 1.improvement.md)
        
        echo "Run towncrier build"
        current_version=$(cd $folder && source .venv/bin/activate && poetry version --short)

        echo "Current version: $current_version, updating patch version"
        IFS='.' read -ra version_components <<< "$current_version"

        major_version="${version_components[0]}"
        minor_version="${version_components[1]}"
        patch_version="${version_components[2]}"

        ((patch_version++))
        new_version="$major_version.$minor_version.$patch_version"

        (cd $folder && source .venv/bin/activate && poetry version "$new_version")
        echo "New version: $new_version"
        
        echo "Run towncrier build to increment the patcb version"
        (cd "$folder" && source .venv/bin/activate && towncrier build --yes --version $new_version && rm changelog/1.improvement.md && git add . && echo "committing $(basename "$folder")" && git commit -m "Bumped ocean version to $VERSION for $(basename "$folder")")
    fi
done