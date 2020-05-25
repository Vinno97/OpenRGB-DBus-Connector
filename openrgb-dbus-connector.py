#!/usr/bin/env python3

from OpenRGB.openrgb import OpenRGB
import yaml
import io
import time
import numpy as np

from hook import Action, BaseAction, LedAction

# if __name__ == "__main__":
client = OpenRGB("localhost", 1337)
devices = {}
for i in range(client.controller_count()):
    devices[i] = client.controller_data(device_id=i)

for _, device in devices.items():
    print("{} has {} LED(s)".format(device.name, len(device.leds)))

    # for controller in devices:
    # print(
    #     controller, "ID: " + str(controller.id), controller.type, sep="\n\t",
    # )

color = (255, 0, 0)

led_count = len(devices[0].leds)
cmap = []
for j in range(led_count):
    cmap.append(color)
client.update_leds(cmap, device_id=0)

action = BaseAction(client)
action = LedAction(
    device=0,
    leds=[0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    color=(255, 255, 0),
    wrapped_action=action,
)

base_config = {0: np.asarray([(0, 0, 0)] * len(devices[0].leds))}
action.act(base_config)

# exit(0)

from collections import defaultdict

from pydbus import SessionBus
from gi.repository import GLib
from dbus.mainloop.glib import DBusGMainLoop

from hook import Hook, Trigger, TriggerCondition
from config import HookFactory


with open("hooks.yaml", "r") as f:
    hook_definitons = yaml.safe_load(f)["hooks"]


def signal_handler(*args, **kwargs):
    print(time.time())
    print("args", args)
    print("kwargs", kwargs)


DBusGMainLoop(set_as_default=True)
bus = SessionBus()

hooks = {}

cond = TriggerCondition(
    "${sig_arg0}", "org.gnome.SessionManager", "GetAppId", ["Playing Audio"]
)

# cond.evaluate(bus, {"sig_arg0": "/org/gnome/SessionManager/Inhibitor5"})


for name, definition in hook_definitons.items():
    hooks[name] = HookFactory.create(definition)

for hook in hooks:
    hooks[hook].attach(bus)

print("%d hooks attached" % len(hooks))

# args = defaultdict(lambda: None, definition['signal'])
# bus.subscribe(
#     sender=args['sender'],
#     iface = args['interface'],
#     signal = args['name'],
#     # arg0 = args['arguments'],
#     signal_fired=signal_handler)

# register your signal callback
# bus.add_signal_receiver(
#     signal_handler,
#     # bus_name="org.bluez",
#     dbus_interface="org.gnome.SessionManager",
#     path="/org/gnome/SesssionManager",
#     signal_name="Inhibit",
#     # arg0="/usr/share/skypeforlinux/skypeforlinux",
#     # message_keyword="skype",
# )

# bus.add_match_string('interface=org.gnome.SessionManager, member=Inhibit, arg0=/usr/share/skypeforlinux/skypeforlinux')

# bus.rec

loop = GLib.MainLoop()
loop.run()
