import os


def handle_private_integration_flags():
    print("{{ cookiecutter.is_private_integration }}")
    if "{{ cookiecutter.is_private_integration }}" == "True":
        os.remove("sonar-project.properties")
    if "{{ cookiecutter.is_private_integration }}" == "False":
        os.remove("Dockerfile")
        os.remove(".dockerignore")


if __name__ == "__main__":
    handle_private_integration_flags()
