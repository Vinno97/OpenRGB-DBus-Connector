import abc
from typing import List, Union, Callable
from string import Template
from pydbus.bus import Bus
from pydbus.subscription import Subscription
from utils import substitute_all

import numpy as np


# TODO: Check for which cases this dict extension suffices and where it does not
class Context(dict):
    def __init__(self, parent: dict = None, iterable={}):
        super().__init__(iterable)
        self._parent = parent

    def __len__(self):
        return super().__len__() + self._parent.__len__()

    def __missing__(self, key):
        return self._parent[key] if self._parent else super().__missing__(key)


class BaseAction:
    def __init__(self, client):
        self._client = client

    @property
    def client(self):
        return self._client

    @client.setter
    def client(self, client):
        self._client = client

    def act(self, config):
        for device, cmap in config.items():
            self.client.update_leds(cmap, device_id=device)

    def reset(self, config):
        for device, cmap in config.items():
            self.client.update_leds(cmap, device_id=device)


class NoopAction(BaseAction):
    def __init__(self, debug=True):
        super().__init__(None)
        self.debug = debug

    def act(self, config):
        if self.debug:
            print("(%s): Act!" % id(self))
        super().act(config)

    def reset(self, config):
        if self.debug:
            print("(%s): Reset!" % id(self))


class Action(BaseAction):
    def __init__(self, wrapped_action, client=None):
        client = client if client else wrapped_action.client
        super().__init__(client)
        self._inner_action = wrapped_action

    @property
    def client(self):
        return self._inner_action.client

    @client.setter
    def client(self, client):
        self._inner_action.client = client

    def act(self, config={}):
        self._act(config)
        self._inner_action.act(config)

    def reset(self, config={}):
        self._reset(config)
        self._inner_action._reset(config)

    def _act(self, config):
        pass

    def _reset(self, config):
        pass


class LedAction(Action):
    def __init__(
        self,
        device: int,
        leds: List[int],
        color: List[int],
        wrapped_action,
        client=None,
    ):
        super().__init__(wrapped_action, client)
        self._inner_action = wrapped_action
        self.device = device
        self.leds = leds
        self.color = color

    # TODO Move this functionaility to a place where the current state can be saved in the config
    def set_up_config(self, config):
        led_count = len(self.client.controller_data(device_id=self.device).leds)
        color_dims = 3
        return np.zeros((led_count, color_dims), dtype=np.ubyte)

    def _act(self, config):
        if not self.device in config:
            config[self.device] = self.set_up_config(config)
        config[self.device][self.leds] = [self.color] * len(self.leds)


class DBusVars:
    name: Union[str, Template]
    interface: Union[str, Template]
    path: Union[str, Template]
    member: Union[str, Template]


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
            [self.service, self.path, self.method, self.response, self.arguments,],
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
            print("Subscription Triggered: ", sender, path, interface, name, arguments)
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
        self, bus: Bus, context: dict, callback: Callable[[Context], None]
    ) -> Subscription:
        sub_params = substitute_all(self.sub_params, context)
        print("Subscribing with params:", sub_params)
        return bus.subscribe(
            **sub_params, signal_fired=self.signal_handler(context, bus, callback),
        )


class Hook:
    def __init__(
        self,
        start_trigger,
        end_trigger,
        bus_name: str = "session",
        name: str = None,
        action=NoopAction(),
    ):
        self.bus_name = bus_name
        self.start_trigger = start_trigger
        self.end_trigger = end_trigger
        self.action = action
        self.subscriptions = []
        self.context = {}
        if not name:
            name = id(self)
        self.name = name

    def attach(self, bus: Bus):
        self._attach(bus)

    def _attach(self, bus: Bus) -> Subscription:
        return self.start_trigger.attach(
            bus, self.context, self.get_trigger_handler(bus)
        )

    # TODO: Clean this method up
    def get_trigger_handler(self, bus):
        def trigger_func(context):
            print(f"Hook '{self.name}' activated")

            self.action.act()
            end_subscription: Subscription = None

            def _on_end(*args, **kwargs):
                end_subscription.disconnect()
                self.action.reset()
                print(f"Hook '{self.name}' halted")

            end_subscription = self.end_trigger.attach(bus, context, _on_end)

        return trigger_func
