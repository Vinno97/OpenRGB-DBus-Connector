from functools import partial
from string import Template
from typing import Dict, List, Union


def substitute_all(
    templates: Union[Template, List[Template], Dict[object, Template]], parameters: dict
) -> Union[str, List[str], Dict[object, str]]:
    if type(templates) is Template:
        return templates.safe_substitute(parameters)
    elif type(templates) is list:
        return [substitute_all(x, parameters) for x in templates]
    elif type(templates) is dict:
        return {k: substitute_all(v, parameters) for k, v in templates.items()}
    else:
        return templates


class Context(dict):
    def __init__(self, parent: dict = {}, iterable={}):
        super().__init__(iterable)
        self._parent = parent

    def __len__(self):
        return super().__len__() + self._parent.__len__()

    def __missing__(self, key):
        return self._parent[key] if self._parent else super().__missing__(key)

    __getattr__ = dict.__getitem__
    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__
