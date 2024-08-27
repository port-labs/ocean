from .types import PunCategory


CATEGORIES = ["sport", "pirate", "dad", "camp"]

PUN_CATEGORIES = [PunCategory(id=x, name=x) for x in CATEGORIES]
