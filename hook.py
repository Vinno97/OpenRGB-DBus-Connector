import abc
from typing import List, Union
from string import Template
from pydbus.bus import Bus
from pydbus.subscription import Subscription
from utils import substitute_all


class BaseAction:
    def __init__(self, client):
        self.client = client

    def act(self, config):
        for device, cmap in config.items():
            self.client.update_leds(cmap, device_id=device)

    def reset(self, config):
        for device, cmap in config.items():
            client.update_leds(cmap, device_id=device)


class NoopAction(BaseAction):
    def __init__(self, debug=True):
        self.debug = debug

    def act(self, config):
        if self.debug:
            print("(%s): Act!" % id(self))
        super().act(config)

    def reset(self):
        if self.debug:
            print("(%s): Reset!" % id(self))


class Action(BaseAction, metaclass=abc.ABCMeta):
    def __init__(self, wrapped_action, client=None):
        client = client if client else wrapped_action.client
        super().__init__(client)
        self._inner_action = wrapped_action

    def act(self, config):
        self._act(config)
        self._inner_action.act(config)

    def reset(self, config):
        self._reset(config)
        self._inner_action._reset(config)

    # @abc.abstractmethod()
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

    def _act(self, config):
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

    def evaluate(self, bus: Bus, context={}) -> bool:
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
        arguments: list = [],
        conditions: List[TriggerCondition] = [],
    ):
        self.sender: str = sender
        self.path: str = path
        self.interface: str = interface
        self.name: str = name
        self.arguments: list = arguments
        self.conditions = conditions
        self.subscription = None

    def evaluate(self, bus: Bus, context={}):
        return all(condition.evaluate(bus, context) for condition in self.conditions)

    def signal_handler(self, bus, callback):
        def handler(sender, path, interface, name, parameters):
            print(sender, path, interface, name, parameters)
            context = {
                "sig_sender": sender,
                "sig_path": path,
                "sig_interface": interface,
                "sig_name": name,
                **{f"sig_arg{i}": v for i, v in enumerate(parameters)},
            }
            if self.evaluate(bus, context):
                callback(sender, path, interface, name, parameters)

        return handler

    def attach(self, bus: Bus, callback) -> Subscription:
        return bus.subscribe(
            sender=self.sender,
            iface=self.interface,
            signal=self.name,
            # arg0 = args['arguments'],
            signal_fired=self.signal_handler(bus, callback),
        )


class Hook:
    bus_name: str
    action: Action
    start_trigger: Trigger
    end_trigger: Trigger

    _bus = None
    _subscription = None

    def __init__(
        self,
        bus_name: str = "session",
        start_trigger: Trigger = Trigger(),
        end_trigger: Trigger = Trigger(),
        action=NoopAction(),
    ):
        self.bus_name = bus_name
        self.start_trigger = start_trigger
        self.end_trigger = end_trigger
        self.action = action

    def attach(self, bus: Bus):
        self._bus = bus

        self._pre_attach(bus)

        self._attach(bus)

        self._post_attach(bus, self._subscription)

    def _attach(self, bus: Bus):
        self.start_trigger.attach(bus, lambda *args, **kwargs: self.action.act())
        self.end_trigger.attach(bus, lambda *args, **kwargs: self.action.reset())

    # Lifecycle hooks
    def _pre_attach(self, bus: Bus):
        pass

    def _post_attach(self, bus: Bus, subscription: Subscription):
        pass

    def _on_signal(self):
        pass
