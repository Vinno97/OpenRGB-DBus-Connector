#!/usr/bin/env python3

import atexit

from openrgbdbus import Connector


connector = Connector.fromConfig('./configuration.yaml')

def close():
  connector.stop()

atexit.register(close)

connector.start()
