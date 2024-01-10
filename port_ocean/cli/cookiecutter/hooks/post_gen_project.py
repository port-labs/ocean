import os


def delete_docker_files():
    if "{{ cookiecutter.remove_docker_files }}" == "True":
        os.remove("Dockerfile")
        os.remove(".dockerignore")


if __name__ == "__main__":
    delete_docker_files()
