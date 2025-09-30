from enum import Enum


class ObjectKind(str, Enum):
    """Enumeration of ArmorCode object kinds."""

    PRODUCT = "product"
    SUB_PRODUCT = "sub-product"
    FINDING = "finding"
