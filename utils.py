from typing import List, Dict, Union
from string import Template


def substitute_all(
    templates: Union[Template, List[Template], Dict[object, Template]], parameters: dict
) -> Union[str, List[str], Dict[object, str]]:
    if type(templates) is Template:
        return templates.substitute(parameters)
    elif type(templates) is list:
        return [substitute_all(x, parameters) for x in templates]
    elif type(templates) is dict:
        return {k: substitute_all(v, parameters) for k, v in templates}
    else:
        raise Exception("Cannot substitute elements of type %s" % str(type(templates)))
