# Running the Ocean image locally using vscode / Cursor

In order to run the local image of Ocean you need to follow these steps:

1. Build the image:

    ```bash
    docker build -f integrations/_infra/Dockerfile.local --build-arg BUILD_CONTEXT=integrations/<integration_type> --platform linux/arm64 -t <my-local-image>:<local> .
    ```

2. Run the image
   1. `5678` is the debugpy port mentioned in the `entry_local.sh` file
   2. `8000` is the port of the Ocean FastAPI server
   3. the `-v` option mounts your local Ocean directory to the pod, allowing you not to constantly build the image.
      1. Make sure to run the command from the root directory of the Ocean repository.

    ```bash
    docker run --rm -it \
    -v $(pwd):/app \
    -p 5678:5678 \
    -p 8000:8000 \
    -e BUILD_CONTEXT=integrations/<integration_type> \
    -e OCEAN__PORT__CLIENT_ID=<MY_CLIENT_ID> \
    -e OCEAN__PORT__CLIENT_SECRET=<MY_CLIENT_SECRET> \
    -e OCEAN__PORT__MY_OTHER_CONFIGURATION=<MY_OTHER_CONFIGURATION> \
    <my-local-image>:<local>
    ```

3. In vscode/Cursor, run the `Attach to docker fake-integration integration` Running configuration from the `launch.json`.
4. Have fun debugging!
