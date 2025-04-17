from setuptools import setup, find_packages

setup(
    name="custom-api",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[],
    entry_points={
        "port_ocean.integrations": [
            "custom-api = main"
        ]
    },
)
