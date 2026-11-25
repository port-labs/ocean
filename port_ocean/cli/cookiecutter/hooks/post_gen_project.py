import os
import shutil


def add_shared_ruff_config() -> None:
    pyproject_path = "pyproject.toml"
    if not os.path.exists(pyproject_path):
        return
    with open(pyproject_path, encoding="utf-8") as file:
        content = file.read()
    if "[tool.ruff]" in content:
        return
    block = (
        "[tool.ruff]\n"
        'extend = "../../ruff.toml"\n'
        "\n"
    )
    marker = "[tool.pydantic-mypy]"
    if marker not in content:
        raise RuntimeError(f"Expected {marker} in generated pyproject.toml")
    updated = content.replace(marker, block + marker, 1)
    with open(pyproject_path, "w", encoding="utf-8") as file:
        file.write(updated)


def handle_private_integration_flags():
    target_dir = os.path.join(
        "{{cookiecutter._output_dir}}", "{{cookiecutter.integration_slug}}"
    )
    root_dir = os.path.join("{{ cookiecutter._repo_dir }}", "../../../")
    infra_make_file = os.path.join(root_dir, "integrations/_infra/Makefile")
    infra_dockerfile = os.path.join(root_dir, "integrations/_infra/Dockerfile.Deb" if "{{ cookiecutter.is_private_integration }}" != "True" else "integrations/_infra/Dockerfile.private.Deb")
    infra_dockerignore = os.path.join(
        root_dir, "integrations/_infra/Dockerfile.dockerignore"
    )
    infra_certs_script = os.path.join(root_dir, "integrations/_infra/sync_ca_certs.sh")
    infra_init_script = os.path.join(root_dir, "integrations/_infra/init.sh")

    target_link_make_file = os.path.join(target_dir, "./Makefile")
    target_link_dockerfile = os.path.join(target_dir, "./Dockerfile")
    target_link_dockerignore = os.path.join(target_dir, "./.dockerignore")
    target_link_certs_script = os.path.join(target_dir, "./_infra/sync_ca_certs.sh")
    target_link_init_script = os.path.join(target_dir, "./_infra/init.sh")

    if "{{ cookiecutter.is_private_integration }}" == "True":
        os.makedirs(os.path.join(target_dir, "./_infra"), exist_ok=True)
        shutil.copyfile(infra_certs_script, target_link_certs_script)
        shutil.copyfile(infra_init_script, target_link_init_script)
        shutil.copyfile(infra_make_file, target_link_make_file)
        shutil.copyfile(infra_dockerfile, target_link_dockerfile)
        shutil.copyfile(infra_dockerignore, target_link_dockerignore)
        return

    os.symlink(infra_make_file, target_link_make_file)


if __name__ == "__main__":
    add_shared_ruff_config()
    handle_private_integration_flags()
    if os.path.exists(".env.development"):
        shutil.move(".env.development", ".env")
