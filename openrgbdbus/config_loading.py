import abc
from typing import Generic, TypeVar

from .actions import Action, BaseAction, LedAction, NoopAction
from .hook import Hook
from .trigger import Trigger, TriggerCondition

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
    def create(cls, definition, **extra_kwargs) -> T:
        kwargs = {}
        factories = cls.field_factories()
        for key, value in definition.items():
            arg_name, factory_func = factories[key]
            # TODO: Don't make this dependant on the name 'kwargs'
            if arg_name == "kwargs":
                kwargs = {**kwargs, **factory_func(value)}
            else:
                kwargs[arg_name] = factory_func(value)
        return cls.construct_instance(**kwargs, **extra_kwargs)

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
                last_item = func(definition, **{arg_name: last_item})
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


class ActionFactory(Factory[Action]):
    @classmethod
    def field_factories(cls):
        return {
            "device_id": ("device", int),
            "leds": ("leds", Factory.list(int)),
            "color": ("color", Factory.list(int)),
            "arguments": ("arguments", Factory.list(str)),
        }

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
            "action": ("action", ActionFactory.create),
            "actions": (
                "action",
                Factory.reduce(ActionFactory.create,
                               "wrapped_action", NoopAction),
            ),
            "trigger": ("start_trigger", TriggerFactory.create),
            "until": ("end_trigger", TriggerFactory.create),
        }

    @classmethod
    def construct_instance(cls, *args, **kwargs):
        return Hook(*args, **kwargs)
