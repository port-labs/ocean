import os


def handle_private_integration_flags():
    if "{{ cookiecutter.is_private_integration }}" == "True":
        os.remove("Dockerfile")
        os.remove(".dockerignore")
    if "{{ cookiecutter.is_private_integration }}" == "False":
        os.remove("sonar-project.properties")


if __name__ == "__main__":
    handle_private_integration_flags()
