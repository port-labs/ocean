#!/bin/bash

# Loop through each folder in the 'integrations' directory
for folder in "$(pwd)"/integrations/*; do
    if [ -d "$folder" ]; then
        if [ ! -f "$folder"/pyproject.toml ]; then
            continue
        fi

        echo "============================"
        echo "Upgrading integration $folder"
        echo "============================"

        (
            cd "$folder" || exit

            echo "Run 'make install'"
            (cd "$folder" && make install)


            # Activate virtual environment if it exists
            if [ -f .venv/bin/activate ]; then
                source .venv/bin/activate
            else
                echo "No virtual environment found in $folder"
                continue
            fi

            # Upgrade dependencies using Poetry
            echo "Running 'poetry update'"
            if ! poetry update; then
                echo "Failed to update dependencies in $folder"
                continue
            fi

            # Get current version and increment patch version
            current_version=$(poetry version --short)
            echo "Current version: $current_version, updating patch version"

            IFS='.' read -ra version_components <<< "$current_version"
            major_version="${version_components[0]}"
            minor_version="${version_components[1]}"
            patch_version="${version_components[2]}"
            ((patch_version++))
            new_version="$major_version.$minor_version.$patch_version"

            # Update to new version
            echo "Set new version: $new_version"
            poetry version "$new_version"

            # Create changelog entry
            echo "Creating changelog entry with Towncrier"
            towncrier create --content "Upgraded integration dependencies" 1.improvement.md

            # Build changelog
            echo "Building changelog"
            towncrier build --yes --version $new_version

            # Remove temporary changelog file
            rm changelog/1.improvement.md

            # Add changes to git and commit
            git add .
            git commit -m "Upgraded dependencies and bumped version to $new_version for $(basename "$folder")"

            # Deactivate virtual environment
            deactivate
        )
    fi
done
