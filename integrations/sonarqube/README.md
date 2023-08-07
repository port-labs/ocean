# sonarqube

SonarQube projects and analysis

## Development Requirements

- Python3.11.0
- Poetry (Python Package Manager)
- Port-Ocean

## Installation

```sh
make install
```

## Runnning Localhost
```sh
make run
```
or
```sh
ocean sail
```

## Running Tests

`make test`

## Access Swagger Documentation

> <http://localhost:8080/docs>

## Access Redoc Documentation

> <http://localhost:8080/redoc>


## Folder Structure
The sonarqube integration suggested folder structure is as follows:

```
sonarqube/
├─ main.py
├─ pyproject.toml
└─ Dockerfile
```