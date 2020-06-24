#!/usr/bin/env python3

import argparse
import atexit

from openrgbdbus import Connector

parser = argparse.ArgumentParser(description="Process some integers.")
parser.add_argument(
    "configuration",
    type=str,
    nargs="?",
    default="./configuration.yaml",
    help="The location of the configuration file",
)

args = parser.parse_args()

connector = Connector.fromConfig(args.configuration)


def close():
    connector.stop()


atexit.register(close)

connector.start()
