#!/usr/bin/env python3

import io
import time
from collections import defaultdict

import numpy as np
import yaml
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib
from pydbus import SessionBus

from config import HookFactory
from hook import Action, BaseAction, Hook, LedAction, Trigger, TriggerCondition
from OpenRGB.openrgb import OpenRGB

# if __name__ == "__main__":
client = OpenRGB("localhost", 1337)
devices = {}
for i in range(client.controller_count()):
    devices[i] = client.controller_data(device_id=i)

for _, device in devices.items():
    print("{} has {} LED(s)".format(device.name, len(device.leds)))

with open("hooks.yaml", "r") as f:
    hook_definitons = yaml.safe_load(f)["hooks"]

DBusGMainLoop(set_as_default=True)
bus = SessionBus()

hooks = {}

for name, definition in hook_definitons.items():
    hook = HookFactory.create(definition, name=name)
    # TODO: Implement a better way to pass the client to actions
    hook.action.client = client
    hooks[name] = hook

for hook in hooks:
    hooks[hook].attach(bus)

print("%d hooks attached" % len(hooks))

loop = GLib.MainLoop()
loop.run()
