import collections.abc
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


# From https://gist.github.com/angstwad/bf22d1822c38a92ec0a9#gistcomment-3305932
def dict_merge(*args, add_keys=True):
    assert len(args) >= 2, "dict_merge requires at least two dicts to merge"
    rtn_dct = args[0].copy()
    merge_dicts = args[1:]
    for merge_dct in merge_dicts:
        if add_keys is False:
            merge_dct = {
                key: merge_dct[key] for key in set(rtn_dct).intersection(set(merge_dct))
            }
        for k, v in merge_dct.items():
            if not rtn_dct.get(k):
                rtn_dct[k] = v
            elif k in rtn_dct and type(v) != type(rtn_dct[k]):
                raise TypeError(
                    f"Overlapping keys exist with different types: original is {type(rtn_dct[k])}, new value is {type(v)}"
                )
            elif isinstance(rtn_dct[k], dict) and isinstance(
                merge_dct[k], collections.abc.Mapping
            ):
                rtn_dct[k] = dict_merge(rtn_dct[k], merge_dct[k], add_keys=add_keys)
            elif isinstance(v, list):
                for list_value in v:
                    if list_value not in rtn_dct[k]:
                        rtn_dct[k].append(list_value)
            else:
                rtn_dct[k] = v
    return rtn_dct
