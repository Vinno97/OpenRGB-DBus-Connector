import logging

from packaging import version

from . import load_configuration
from .object_factories import ConnectorFactory


class ConfigurationParser:
    _config_ver = "0.4.0"

    def __init__(self):
        super().__init__()
        self.configuration = None

    def load(self, configuration):
        if isinstance(configuration, str):
            # Load the configuration file if a string (assumed path) is provided
            self.configuration = load_configuration(configuration)
        else:
            # Else assume the argument is the already parsed configuration
            self.configuration = configuration
        return self

    def createConnector(
        self, create_key,
    ):
        if not self.configuration:
            raise Exception("createConnector() was called before load()")
        configuration = self.configuration

        assert version.parse(self._config_ver) >= version.parse(
            configuration["version"]
        )

        # TODO: Only set logging for openrgbdbus module
        if "logging" in configuration:
            numeric_level = getattr(logging, configuration["logging"].upper(), None)
            if not isinstance(numeric_level, int):
                raise ValueError("Invalid log level: %s" % configuration["logging"])
            logging.basicConfig(level=numeric_level)

        return ConnectorFactory.create(configuration, create_key=create_key)
