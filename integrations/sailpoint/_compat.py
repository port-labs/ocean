import importlib
import pkgutil

import port_ocean

CANDIDATES = [
    "port_ocean.contexts",
    "port_ocean.context",
    "port_ocean.core.contexts",
    "port_ocean.core.context",
    "port_ocean.runtime.context",
    "port_ocean.app.context",
]


def _available_port_ocean_modules():
    try:
        return [m.name for m in pkgutil.iter_modules(port_ocean.__path__)]
    except Exception:
        return []


_last_err = None
for mod in CANDIDATES:
    try:
        m = importlib.import_module(mod)
        if hasattr(m, "ocean"):
            ocean = getattr(m, "ocean")
            break
    except Exception as e:
        _last_err = e
else:
    avail = ", ".join(sorted(_available_port_ocean_modules()))
    raise ImportError(
        "Could not locate `ocean` in port_ocean. "
        f"Tried: {CANDIDATES}. "
        f"Available top-level submodules under port_ocean: [{avail}]. "
        f"Last error: {_last_err}"
    )
