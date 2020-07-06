import collections.abc
import math
from functools import partial
from string import Template as StringTemplate
from typing import Dict, List, Union

import regex as re
from jinja2 import Template
from openrgb.utils import RGBColor


def substitute_all(
    templates: Union[StringTemplate, Template, List[Template], Dict[object, Template]],
    parameters: dict,
) -> Union[str, List[str], Dict[object, str]]:
    if isinstance(templates, Template):
        return templates.render(
            **parameters, utils={"temperature_to_rgb": temperature_to_rgb}
        )
    if isinstance(templates, StringTemplate):
        return templates.safe_substitute(parameters)
    elif isinstance(templates, list):
        return [substitute_all(x, parameters) for x in templates]
    elif isinstance(templates, dict):
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


def temperature_to_rgb(kelvin):
    temp = kelvin / 100
    red, green, blue = 0, 0, 0

    if temp <= 66:
        red = 255
        green = temp
        green = 99.4708025861 * math.log(green) - 161.1195681661

        if temp <= 19:
            blue = 0
        else:
            blue = temp - 10
            blue = 138.5177312231 * math.log(blue) - 305.0447927307

    else:
        red = temp - 60
        red = 329.698727446 * math.pow(red, -0.1332047592)

        green = temp - 60
        green = 288.1221695283 * math.pow(green, -0.0755148492)

        blue = 255

    return clamp(red, 0, 255), clamp(green, 0, 255), clamp(blue, 0, 255)


def clamp(x, min, max):
    if x < min:
        return min
    if x > max:
        return max

    return x


TemplatableList = Union[List[str], str]
ListTemplate = Union[Template, List[Union[Template, object]]]


def list_to_template(val: TemplatableList):
    if isinstance(val, list):
        return [Template(x) if isinstance(x, str) else x for x in val]
    return Template(val)


def list_from_template(template: ListTemplate, context):
    substituted = substitute_all(template, context)
    if isinstance(substituted, str):
        # Split the values if they're formatted like a list or tuple (or just splitted by a comma)
        # Maybe this should be made to be more robust in the future
        substituted = [
            x.strip() for x in substituted.lstrip("[(").rstrip("])").split(",")
        ]
    return substituted


def color_from_template(template: ListTemplate, context: Context):
    return RGBColor(*(int(float(x)) for x in list_from_template(template, context)))
