import os


def handle_custom_integration_flags():
    if "{{ cookiecutter.custom_integration }}" == "False":
        os.remove("Dockerfile")
        os.remove(".dockerignore")
    if "{{ cookiecutter.custom_integration }}" == "True":
        os.remove("sonar-project.properties")


if __name__ == "__main__":
    handle_custom_integration_flags()
