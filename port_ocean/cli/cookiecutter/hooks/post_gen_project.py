import os


def delete_docker_files():
    if "{{ cookiecutter.remove_docker_files }}" == "true":
        os.remove("Dockerfile")
        os.remove(".dockerignore")

def delete_sonarcloud_files():
    if "{{ cookiecutter.custom_integration }}" == "true":
        os.remove("sonar-project.properties")

if __name__ == "__main__":
    delete_docker_files()
    delete_sonarcloud_files()