import abc
import asyncio
import logging
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
            [self.service, self.path, self.method, self.response, self.arguments,],
            parameters=context,
        )

        dev = bus.get(service, path)
        func = getattr(dev, method)
        result = func(*arguments)
        return result == expected_response


class TriggerSubscription:
    def __init__(self, on_cancel):
        super().__init__()
        self._on_cancel = on_cancel

    def cancel(self):
        self._on_cancel()


class TriggerSource(metaclass=abc.ABCMeta):
    def __init__(self):
        super().__init__()

    @abc.abstractmethod
    def subscribe(
        self, bus: Bus, context: Context, callback: TriggerCallback
    ) -> TriggerSubscription:
        pass


class Trigger:
    def __init__(
        self, source: TriggerSource, conditions: List[TriggerCondition] = [],
    ):
        self.source = source
        self.conditions = conditions

    def evaluate_conditions(self, bus: Bus, context: Context) -> bool:
        return all(condition.evaluate(bus, context) for condition in self.conditions)

    def subscribe(
        self, bus: Bus, context: Context, callback: TriggerCallback
    ) -> TriggerSubscription:
        def callback_wrapper(*args, **kwargs):

            try:
                if self.evaluate_conditions(bus, context):
                    callback(*args, **kwargs)
            except Exception as ex:
                logging.critical("Unhandled exception in callback task: ", exc_info=ex)
                exit(1)

        return self.source.subscribe(bus, context, callback_wrapper)


class DBusTrigger(TriggerSource):
    def __init__(
        self,
        sender: str = None,
        path: str = None,
        interface: str = None,
        name: str = None,
        eavesdrop: bool = False,
        destination: str = None,
        arguments: List = [],
        conditions: List[TriggerCondition] = [],
    ):
        super().__init__()

        self.sub_params = {}

        if sender:
            self.sub_params["sender"] = Template(sender)
        if path:
            self.sub_params["path"] = Template(path)
        if interface:
            self.sub_params["interface"] = Template(interface)
        if name:
            self.sub_params["member"] = Template(name)
        if destination:
            if eavesdrop:
                self.sub_params["destination"] = Template(destination)
            else:
                print(
                    "'hook.destination' should only be used together with 'hook.eavesdrop. Ignoring..."
                )
        if eavesdrop:
            self.sub_params["eavesdrop"] = str(eavesdrop).lower()
        self.arguments = [Template(x) if isinstance(x, str) else x for x in arguments]

    # TODO: Clean this method ups

    def create_filter(self, context: Context, bus: Bus, callback: TriggerCallback):
        async def make_callback(*args, **kwargs):
            callback(*args, **kwargs)

        event_loop = asyncio.get_event_loop()

        def filter(conn, message, incoming):
            try:
                if incoming and self._should_handle(message, context):
                    new_context = self.construct_callback_context(context, message)
                    asyncio.run_coroutine_threadsafe(
                        make_callback(new_context), event_loop
                    )
                return message
            except Exception as ex:
                logging.critical("Unhandled exception in filter thread: ", exc_info=ex)
                exit(1)

        return filter

    def construct_callback_context(self, context: Context, message) -> Context:
        return Context(
            context,
            {
                "sig_sender": message.get_sender(),
                "sig_path": message.get_path(),
                "sig_interface": message.get_interface(),
                "sig_name": message.get_member(),
                "sig_destination": message.get_destination(),
                **{f"sig_arg{i}": v for i, v in enumerate(message.get_body().unpack())},
            },
        )

    def subscribe(
        self, bus: Bus, context: Context, callback: TriggerCallback
    ) -> TriggerSubscription:

        sub_params = substitute_all(self.sub_params, context)
        logging.info("Subscribing with params: %s", sub_params)

        match_string = ", ".join(
            ["{}={}".format(name, val) for name, val in sub_params.items()]
        )

        bus.get("org.freedesktop.DBus").AddMatch(match_string)
        _filter = bus.con.add_filter(self.create_filter(context, bus, callback))

        def unsubscribe(_filter=_filter, bus=bus):
            bus.con.remove_filter(_filter)
            bus.get("org.freedesktop.DBus").RemoveMatch(match_string)

        return TriggerSubscription(unsubscribe)

    def _should_handle(self, message, context: Context) -> bool:
        """Check if the trigger should be tripped by the message"""

        message_params = {
            "sender": message.get_sender(),
            "path": message.get_path(),
            "interface": message.get_interface(),
            "member": message.get_member(),
            "destination": message.get_destination(),
        }
        logging.debug("Analyzing incoming message %s", message_params)
        sub_params = substitute_all(self.sub_params, context)

        for key in (k for k in sub_params if k != "eavesdrop"):
            expected = sub_params[key]
            actual = message_params[key]
            if expected and expected != actual:
                # logging.debug(
                #     f"Ignoring message due to {key} mismatch (expected {expected}, got {actual})"
                # )
                return False

        if not self._validate_arguments(message, context):
            return False

        logging.debug("Accepted incoming message %s", message_params)

        # If everything was alright: return True
        return True

    def _validate_arguments(self, message, context) -> bool:
        actual_args = message.get_body().unpack()
        expected_args = substitute_all(self.arguments, context)
        argument_pairs = zip(expected_args, actual_args)
        filtered_pairs = ((e, a) for e, a in argument_pairs if e != None)
        for expected_arg, actual in filtered_pairs:
            if expected_arg != actual:
                # logging.debug(
                #     f"Ignoring message due to argument mismatch (expected {expected_args}, got {actual})"
                # )
                return False
        return True


class SleepTrigger(TriggerSource):
    def __init__(self, duration):
        super().__init__()
        self.duration = duration

    def _on_activate(self, bus: Bus, context: Context):
        pass

    def subscribe(
        self, bus: Bus, context: Context, callback: TriggerCallback
    ) -> TriggerSubscription:
        async def trigger():
            await asyncio.sleep(self.duration)
            logging.debug("Sleep trigger activated after %d seconds", self.duration)
            callback(context)

        task = asyncio.get_event_loop().create_task(trigger())
        return TriggerSubscription(lambda task=task: task.cancel())
