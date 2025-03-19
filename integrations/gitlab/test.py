import gc
from copy import deepcopy

some_data = {"a": 1, "b": 2}

my_object = deepcopy(some_data)
another_ref = my_object
referrers = gc.get_referrers(my_object)
print(referrers)


## results
# [{'__name__': '__main__', '__doc__': None, '__package__': None, '__loader__': <_frozen_importlib_external.SourceFileLoader object at 0x100a19940>, '__spec__': None, '__annotations__': {}, '__builtins__': <module 'builtins' (built-in)>, '__file__': '/Users/chael/Desktop/CODE/Port/ocean/integrations/gitlab/test.py', '__cached__': None, 'gc': <module 'gc' (built-in)>, 'deepcopy': <function deepcopy at 0x100a7c400>, 'some_data': {'a': 1, 'b': 2}, 'my_object': {'a': 1, 'b': 2}, 'referrers': [...]}]

## explanation:
# The referrers list contains a single item, which is a dictionary that contains the variables in the current module.
# This indicates that the variable my_object is referenced only by variables in the current module.
# The referrers list does not contain any other references to the my_object variable.
# This suggests that the my_object variable is not referenced by any other objects in the Python runtime environment.
