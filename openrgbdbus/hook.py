from string import Template
from typing import Callable, List, Union

from pydbus.bus import Bus, bus_get
from pydbus.subscription import Subscription

from .actions import Action
from .trigger import DBusTrigger
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
        start_trigger: DBusTrigger,
        end_trigger: DBusTrigger,
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

    def set_context(self, context: Context):
        self.context = Context(context)

    def attach(self):
        self.start_trigger.activate(
            self.bus, self.context, self.get_trigger_handler(self.bus)
        )

    def disconnect(self):
        # TODO: Add back functionality to clean up subscriptions (delegate to triggers)
        pass

    # TODO: Clean this method up
    def get_trigger_handler(self, bus):
        def trigger_func(context):
            print(f"Hook '{self.name}' activated")

            self.action.act(context)
            # end_subscription: Subscription = None

            def _on_end(*args, **kwargs):
                # end_subscription.disconnect()
                # self.subscriptions.remove(end_subscription)
                self.action.reset(context)
                print(f"Hook '{self.name}' halted")

            self.end_trigger.activate(bus, context, _on_end)

        return trigger_func
