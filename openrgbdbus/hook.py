import abc
from string import Template
from typing import Callable, List, Union

from pydbus.bus import Bus, bus_get
from pydbus.subscription import Subscription

from .actions import Action
from .trigger import Trigger
from .utils import substitute_all


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
        self.subscriptions: List[Subscription] = []
        self.context = {}
        if not name:
            name = id(self)
        self.name = name

    def attach(self):
        self.subscriptions.append(self.start_trigger.attach(
            self.bus, self.context, self.get_trigger_handler(self.bus)
        ))

    # TODO: This responsibility should probably be delegated to the trigger
    def disconnect(self):
        for subscription in self.subscriptions:
            subscription.disconnect()

    # TODO: Clean this method up
    def get_trigger_handler(self, bus):
        def trigger_func(context):
            print(f"Hook '{self.name}' activated")

            self.action.act()
            end_subscription: Subscription = None

            def _on_end(*args, **kwargs):
                end_subscription.disconnect()
                self.subscriptions.remove(end_subscription)
                self.action.reset()
                print(f"Hook '{self.name}' halted")

            end_subscription = self.end_trigger.attach(bus, context, _on_end)

        return trigger_func
