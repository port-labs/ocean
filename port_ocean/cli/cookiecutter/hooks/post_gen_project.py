import os
import shutil


def handle_private_integration_flags():
    infra_make_file = "../_infra/Makefile"
    target_link_make_file = os.path.join("./Makefile")

    if "{{ cookiecutter.is_private_integration }}" == "True":
        shutil.copyfile(infra_make_file, target_link_make_file)
        os.remove("sonar-project.properties")
        return

    os.symlink(infra_make_file, target_link_make_file)
    os.remove("Dockerfile")
    os.remove(".dockerignore")


if __name__ == "__main__":
    handle_private_integration_flags()
