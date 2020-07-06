import logging
from typing import Callable, List, Union

from jinja2 import Template
from pydbus.bus import Bus, bus_get
from pydbus.subscription import Subscription

from .actions import Action
from .trigger import Trigger, TriggerSubscription
from .utils import Context, substitute_all


def bus_from_name(name: str):
    name = name.lower()
    if name == "system":
        bus_type = Bus.Type.SYSTEM
    elif name == "session":
        bus_type = Bus.Type.SESSION
    else:
        # Just because I currently do not know how they work
        raise Exception("Custom busses are currently not supported")
    return bus_get(bus_type)


class Hook:
    def __init__(
        self,
        start_trigger: Trigger,
        end_trigger: Trigger,
        action: Action,
        bus_name: str = "session",
        name: str = None,
    ):
        self.bus = bus_from_name(bus_name)
        self.start_trigger = start_trigger
        self.end_trigger = end_trigger
        self.action = action
        self.context = {}
        if not name:
            name = id(self)
        self.name = name
        self.subscriptions: List[TriggerSubscription] = []

    def set_context(self, context: Context):
        self.context = Context(context)

    def attach(self):
        self.subscriptions.append(
            self.start_trigger.subscribe(
                self.bus, self.context, self._get_trigger_handler(self.bus)
            )
        )

    def disconnect(self):
        for subscription in self.subscriptions:
            self._cancel_subscription(subscription)

    def _cancel_subscription(self, subscription: TriggerSubscription):
        subscription.cancel()
        self.subscriptions.remove(subscription)

    def _get_trigger_handler(self, bus):
        def trigger_func(context):
            logging.info(f"Hook '{self.name}' activated")

            action_cookie = self.action.act(context)

            def _on_end(*args, **kwargs):
                self.action.reset(action_cookie, context)
                logging.info(f"Hook '{self.name}' halted")
                self._cancel_subscription(subscription)

            subscription = self.end_trigger.subscribe(bus, context, _on_end)
            self.subscriptions.append(subscription)

        return trigger_func
