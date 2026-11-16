from enum import StrEnum


class ObjectKind(StrEnum):
    PROJECT = "project"
    PROMPT = "prompt"
    DATASET = "dataset"
    MODEL = "model"
