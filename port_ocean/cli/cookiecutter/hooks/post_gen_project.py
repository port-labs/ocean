import os
import shutil


def handle_private_integration_flags():
    target_dir = os.path.join(
        "{{cookiecutter._output_dir}}", "{{cookiecutter.integration_slug}}"
    )
    root_dir = os.path.join("{{ cookiecutter._repo_dir }}", "../../../")
    infra_make_file = os.path.join(root_dir, "integrations/_infra/Makefile")
    infra_dockerfile = os.path.join(root_dir, "integrations/_infra/Dockerfile.Deb")
    infra_dockerignore = os.path.join(
        root_dir, "integrations/_infra/Dockerfile.dockerignore"
    )
    target_link_make_file = os.path.join(target_dir, "./Makefile")
    target_link_dockerfile = os.path.join(target_dir, "./Dockerfile")
    target_link_dockerignore = os.path.join(target_dir, "./.dockerignore")

    if "{{ cookiecutter.is_private_integration }}" == "True":
        shutil.copyfile(infra_make_file, target_link_make_file)
        shutil.copyfile(infra_dockerfile, target_link_dockerfile)
        shutil.copyfile(infra_dockerignore, target_link_dockerignore)
        os.remove("sonar-project.properties")
        return

    os.symlink(infra_make_file, target_link_make_file)


if __name__ == "__main__":
    handle_private_integration_flags()
