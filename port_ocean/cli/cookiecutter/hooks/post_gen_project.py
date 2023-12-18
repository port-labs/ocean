import os


def delete_docker_files():
    if "{{ cookiecutter.public_integration }}" == "True":
        os.remove("Dockerfile")
        os.remove(".dockerignore")


if __name__ == "__main__":
    delete_docker_files()
