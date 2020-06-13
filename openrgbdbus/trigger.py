import abc
from string import Template
from typing import Callable, List, Union

from pydbus.bus import Bus
from pydbus.subscription import Subscription

from .utils import Context, substitute_all


class TriggerCondition:
    def __init__(
        self,
        service: str,
        path: str,
        method: str,
        response: str,
        # interface: str = None,
        arguments: [] = [],
    ):
        self.service = Template(service)
        self.path = Template(path)
        # self.interface = Template(interface)
        self.method = Template(method)
        self.response = Template(response)
        # self.response = [Template(x) for x in response]
        self.arguments = [Template(x) for x in arguments]

    def evaluate(self, bus: Bus, context: Context) -> bool:
        service, path, method, expected_response, arguments = substitute_all(
            [self.service, self.path, self.method,
                self.response, self.arguments, ],
            parameters=context,
        )

        dev = bus.get(service, path)
        func = getattr(dev, method)
        result = func(*arguments)
        return result == expected_response


class Trigger:
    def __init__(
        self,
        sender: str = None,
        path: str = None,
        interface: str = None,
        name: str = None,
        arguments: List[str] = [],
        conditions: List[TriggerCondition] = [],
    ):
        self.sub_params = {}

        if sender:
            self.sub_params["sender"] = Template(sender)
        if path:
            self.sub_params["object"] = Template(path)
        if interface:
            self.sub_params["iface"] = Template(interface)
        if name:
            self.sub_params["signal"] = Template(name)
        self.arguments = [Template(x) for x in arguments]
        self.conditions = conditions
        self.subscription = None

    def evaluate(self, bus: Bus, context={}):
        return all(condition.evaluate(bus, context) for condition in self.conditions)

    # TODO: Clean this method up
    def signal_handler(
        self, context: Context, bus: Bus, callback: Callable[[Context], None]
    ):
        def handler(sender, path, interface, name, arguments):
            print("Subscription Triggered: ", sender,
                  path, interface, name, arguments)
            expected_arguments = substitute_all(self.arguments, context)
            for expected, actual in zip(expected_arguments, arguments):
                if expected != actual:
                    print(
                        f"Ignoring due to argument mismatch (expected {expected}, got {actual})"
                    )
                    return

            new_context = Context(context)
            new_context.update(
                {
                    "sig_sender": sender,
                    "sig_path": path,
                    "sig_interface": interface,
                    "sig_name": name,
                    **{f"sig_arg{i}": v for i, v in enumerate(arguments)},
                }
            )
            if self.evaluate(bus, new_context):
                callback(new_context)

        return handler

    def attach(
        self, bus: Bus, context: Context, callback: Callable[[Context], None]
    ) -> Subscription:
        sub_params = substitute_all(self.sub_params, context)
        print("Subscribing with params:", sub_params)
        return bus.subscribe(
            **sub_params, signal_fired=self.signal_handler(context, bus, callback),
        )
