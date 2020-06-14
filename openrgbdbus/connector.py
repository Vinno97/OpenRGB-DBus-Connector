import abc

import yaml
from gi.repository import GLib
from packaging import version
from pydbus import SessionBus

from .initialization import ConnectorFactory

_config_ver = '0.1.1'


class Connector():
    __create_key = object()

    @classmethod
    def fromConfig(cls, configuration):
        if isinstance(configuration, str):
            # Load the configuration file if a string (assumed path) is provided
            with open(configuration, "r") as f:
                definition = yaml.safe_load(f)
        else:
            # Else assume the argument is the already parsed configuration
            definition = configuration
        assert(version.parse(_config_ver) >=
               version.parse(definition['version']))

        return ConnectorFactory.create(definition, create_key=cls.__create_key, client=None)

    def __init__(self, create_key, hooks, client):
        assert(create_key == Connector.__create_key), \
            "Connector objects must be created using Connector.fromConfig"
        self.hooks = hooks
        self.client = client
        self.loop = GLib.MainLoop()

    def start(self):
        for name, hook in self.hooks.items():
            hook.attach()

        print("%d hooks attached" % len(self.hooks))

        self.loop.run()

    def stop(self):
        self.loop.quit()

        for name, hook in self.hooks.items():
            hook.disconnect()

        print("%d hooks removed" % len(self.hooks))
