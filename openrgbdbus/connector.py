import asyncio

from gi.repository import GLib
from pydbus import SessionBus

from openrgbdbus.actions import Action, ActionStack

from .configuration import ConfigurationParser
from .utils import Context


class Connector:
    __create_key = object()

    @classmethod
    def fromConfig(cls, configuration):

        return (
            ConfigurationParser().load(configuration).createConnector(cls.__create_key)
        )

    def __init__(
        self, create_key, hooks, client, debug=False, default_action: Action = None
    ):
        assert (
            create_key == Connector.__create_key
        ), "Connector objects must be created using Connector.fromConfig"
        self.hooks = hooks
        self.client = client
        self.loop = GLib.MainLoop()
        self.default_action = default_action
        self.context = Context(
            {"rgb_client": client, "debug": debug, "action_stack": ActionStack(client),}
        )
        for hook in self.hooks:
            hook.set_context(self.context)

    def start(self):
        # Just call this once to ensure there is a default event loop.
        event_loop = asyncio.get_event_loop()

        if self.default_action:
            self.default_action.act(self.context)
            print("Initialized with default actions")

        for hook in self.hooks:
            hook.attach()

        # asyncio.run(self.context.action_stack.start_animation_loop(30))
        task = event_loop.create_task(self.context.action_stack.start_animation_loop())
        event_loop.run_forever()

        print("%d hooks attached" % len(self.hooks))

        self.loop.run()

    def stop(self):
        self.loop.quit()
        asyncio.get_event_loop().stop()

        for hook in self.hooks:
            hook.disconnect()

        print("%d hooks removed" % len(self.hooks))

        if self.default_action:
            self.default_action.reset(self.context)
            print("Reset default actions")
