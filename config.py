import abc
from typing import TypeVar, Generic
from hook import *

T = TypeVar("T")


class Factory(Generic[T], metaclass=abc.ABCMeta):
    @classmethod
    def field_factories(cls):
        return {}

    @classmethod
    @abc.abstractmethod
    def construct_instance(cls, *args, **kwargs) -> T:
        pass

    @classmethod
    def _construct_kwargs(cls, definition):
        kwargs = {}
        factories = cls.field_factories()
        for key, value in definition.items():
            arg_name, factory_func = factories[key]
            # TODO: Don't make this dependant on the name 'kwargs'
            if arg_name == "kwargs":
                kwargs = {**kwargs, **factory_func(value)}
            else:
                kwargs[arg_name] = factory_func(value)
        return kwargs

    @classmethod
    def create(cls, definition) -> T:
        return cls.construct_instance(**cls._construct_kwargs(definition))

    @classmethod
    def list(cls, func):
        def list_wrapper(definition_list):
            return [func(definition) for definition in definition_list]

        return list_wrapper

    @classmethod
    def reduce(cls, func, arg_name, initial_func):
        def reduce_wrapper(definition_list):
            last_item = initial_func()
            for i, definition in enumerate(definition_list):
                definition = {**definition, "_last_item": last_item}
                last_item = func(definition)
            return last_item

        return reduce_wrapper

    @classmethod
    def dict(cls, fields):
        def dict_wrapper(definition_dict):
            return {
                arg_name: fields[arg_name][1](definition)
                for arg_name, definition in definition_dict.items()
            }

        return dict_wrapper


# TODO: Make this factory proper
# FIXME: Why did I have to make actions decorators :(
class ActionFactory(Factory[Action]):
    @classmethod
    def field_factories(cls):
        return {
            "device_id": ("device", int),
            "leds": ("leds", Factory.list(int)),
            "color": ("color", Factory.list(int)),
            "arguments": ("arguments", Factory.list(str)),
            # HACK: This is sort of a hack. Or is it? Maybe.
            "_last_item": ("wrapped_action", lambda x: x),
        }

    # @classmethod
    # def _construct_kwargs(cls, definition):
    #     kwargs = super()._construct_kwargs(definition)
    #     kwargs["wrapped_action"] = cls.last_instance
    #     return kwargs

    # @classmethod
    # def cascade_list(cls, func, key):
    #     cls.last_instance = BaseAction(None)

    #     def cascading_wrapper(definition_list):
    #         var = [
    #             func({**definition, "_last_instance": cls.last_instance})
    #             for definition in definition_list
    #         ]
    #         return var

    #     return cascading_wrapper

    @classmethod
    def construct_instance(cls, *args, **kwargs):
        # TODO: Don't hardcode the LedAction here
        return LedAction(*args, **kwargs)


class TriggerFactory(Factory[Trigger]):
    @classmethod
    def field_factories(cls):
        return {
            "signal": [
                "kwargs",
                Factory.dict(
                    {
                        "sender": ("sender", str),
                        "path": ("path", str),
                        "interface": ("interface", str),
                        "name": ("name", str),
                        "arguments": ("arguments", Factory.list(str)),
                    }
                ),
            ],
            "conditions": ("conditions", Factory.list(TriggerConditionFactory.create)),
        }

    @classmethod
    def construct_instance(cls, *args, **kwargs):
        return Trigger(*args, **kwargs)


class TriggerConditionFactory(Factory[TriggerCondition]):
    @classmethod
    def field_factories(cls):
        return {
            "service_name": ("service", str),
            "path": ("path", str),
            "method": ("method", str),
            "response": ("response", str),
            "arguments": ("arguments", Factory.list(str)),
        }

    @classmethod
    def construct_instance(cls, *args, **kwargs):
        return TriggerCondition(*args, **kwargs)


class HookFactory(Factory[Hook]):
    @classmethod
    def field_factories(cls):
        return {
            "bus": ("bus_name", str),
            # "action": ("action", ActionFactory.create),
            # "actions": ("action", lambda x: None),
            # "actions": (
            #     "action",
            #     ActionFactory.cascade_list(ActionFactory.create, key="wrapped_action"),
            # ),
            "actions": (
                "action",
                Factory.reduce(ActionFactory.create, "wrapped_action", NoopAction),
            ),
            "trigger": ("start_trigger", TriggerFactory.create),
            "until": ("end_trigger", TriggerFactory.create),
        }

    @classmethod
    def construct_instance(cls, *args, **kwargs):
        return Hook(*args, **kwargs)
