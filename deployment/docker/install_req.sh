#!/bin/bash

folder_path="integrations"

# Iterate over each directory in the "integrations" folder
for directory in "$folder_path"/*; do
  if [[ -d "$directory" ]]; then
    requirements_file="$directory/requirements.txt"
    if [[ -f "$requirements_file" ]]; then
      echo "Installing requirements for $directory" 
      # Perform pip install using the requirements.txt file
      pip3 install -r "$requirements_file"
    fi
  fi
done

pip3 install -r requirements.txt