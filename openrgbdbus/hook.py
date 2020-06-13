import abc
from string import Template
from typing import Callable, List, Union

from pydbus.bus import Bus
from pydbus.subscription import Subscription

from .utils import substitute_all


class Hook:
    def __init__(
        self,
        start_trigger,
        end_trigger,
        action,
        bus_name: str = "session",
        name: str = None,
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
