import abc
import asyncio
from string import Template
from typing import Callable, List, Union

from pydbus.bus import Bus
from pydbus.subscription import Subscription

from .utils import Context, substitute_all

TriggerCallback = Callable[[Context], None]


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


class TriggerSource(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def activate(self, bus: Bus, context: Context, callback: TriggerCallback):
        pass

    # @abc.abstractmethod
    # def deactivate(self):
    #     pass


class Trigger():
    def __init__(
        self,
        source: TriggerSource,
        conditions: List[TriggerCondition] = [],
    ):
        self.source = source
        self.conditions = conditions

    def evaluate_conditions(self, bus: Bus, context: Context) -> bool:
        return all(condition.evaluate(bus, context) for condition in self.conditions)

    def activate(self, bus: Bus, context: Context, callback: TriggerCallback):
        self.source.activate(bus, context, lambda context: callback(
            context) if self.evaluate_conditions(bus, context) else None)

    def deactivate(self):
        self.source.deactivate()


class DBusTrigger(TriggerSource):
    def __init__(
        self,
        sender: str = None,
        path: str = None,
        interface: str = None,
        name: str = None,
        eavesdrop: bool = False,
        arguments: List = [],
        conditions: List[TriggerCondition] = [],
    ):
        self.sub_params = {}

        if sender:
            self.sub_params["sender"] = Template(sender)
        if path:
            self.sub_params["object"] = Template(path)
        if interface:
            self.sub_params["interface"] = Template(interface)
        if name:
            self.sub_params["member"] = Template(name)
        self.sub_params["eavesdrop"] = str(eavesdrop).lower()
        self.arguments = [Template(x) if isinstance(
            x, str) else x for x in arguments]
        self.subscription = None

    # TODO: Clean this method up

    def get_filter(
        self, context: Context, bus: Bus, callback: Callable[[Context], None]
    ):
        # TODO: Try to run this function (or at least its callback) on the main thread
        # TODO: combine the `handler` and `filter` function
        def handler(sender, path, interface, name, arguments):
            if context.debug:
                print(
                    "Subscription Triggered: ", sender, path, interface, name, arguments
                )
            expected_arguments = substitute_all(self.arguments, context)
            argument_pairs = [(e, a) for e, a in zip(
                expected_arguments, arguments) if e != None]
            print(argument_pairs)
            for expected, actual in argument_pairs:
                print(expected)
                if expected != actual and expected != None:
                    if context.debug:
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

            callback(new_context)

        def filter(conn, message, incoming):
            if not incoming:
                return
            sender = message.get_sender()
            path = message.get_path()
            interface = message.get_interface()
            member = message.get_member()
            arguments = message.get_body().unpack()
            handler(sender, path, interface, member, arguments)
        return filter

    def activate(
        self, bus: Bus, context: Context, callback: TriggerCallback
    ):
        sub_params = substitute_all(self.sub_params, context)
        if context.debug:
            print("Subscribing with params:", sub_params)

        match_string = ", ".join(
            ["{}={}".format(name, val) for name, val in sub_params.items()])

        bus.get('org.freedesktop.DBus').AddMatch(match_string)
        bus.con.add_filter(self.get_filter(context, bus, callback))


class SleepTrigger(TriggerSource):
    def __init__(self, duration):
        super().__init__()
        self.duration = duration

    def activate(
        self, bus: Bus, context: Context, callback: TriggerCallback
    ):
        async def trigger():
            await asyncio.sleep(self.duration)
            callback(context)
        asyncio.run(trigger())
