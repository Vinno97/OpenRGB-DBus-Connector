#!/usr/bin/env python3

from openrgbdbus import Connector

connector = Connector.fromConfig('./configuration.yaml')
connector.start()
