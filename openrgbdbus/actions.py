import math
import os
import struct
from typing import List, Union

import numpy as np
from jinja2 import Template
from openrgb import OpenRGBClient
from openrgb.orgb import Device, Zone
from openrgb.utils import DeviceType, RGBColor

from .utils import (
    Context,
    TemplatableList,
    color_from_template,
    dict_merge,
    list_from_template,
    list_to_template,
)

ActionCookie = int
StackState = dict


class ActionStack:
    def __init__(self, client: OpenRGBClient):
        self.client = client
        self.states = []
        self._initialize()

    def _initialize(self):
        base_state = {"cookie": None, "devices": []}
        for key, device in enumerate(self.client.devices):
            device_state = {"id": key, "colors": device.colors}
            base_state["devices"].append(device_state)

        self.states.append(base_state)

        # TODO: Remove this temp thing
        self.base_state = base_state

    def push_state(self, state: StackState) -> ActionCookie:
        state["cookie"] = self._get_cookie()
        self.states.append(state)

        self._update_from_state(state)
        return state["cookie"]

    def remove_state(self, cookie: ActionCookie):
        state = next(
            (state for state in self.states if state["cookie"] == cookie), None
        )

        if state:
            self.states.remove(state)
            # Check what devices should be updated
            self._update_from_state(state)

    def _get_cookie(self):
        """Get a cryptographically secure random cookie
        
           32 bits should be good enough that there's no need the check for duplicate
           ids in the states. (famous last words?)
        """
        return struct.unpack("i", os.urandom(4))

    def _update_from_state(self, state):
        """Updates every device, zone or led that this state effects."""
        for device in state["devices"]:
            if "zones" in device:
                for zone in device["zones"]:
                    self._update_zone(device["id"], zone["id"])
                    if "leds" in zone:
                        for led in zone["leds"]:
                            # TODO: (Re)Setting individual LEDs is not yet supported
                            pass
            if "leds" in device:
                for led in device["leds"]:
                    # TODO: (Re)Setting individual LEDs is not yet supported
                    pass
            if "colors" in device or "color" in device:
                pass  # TODO: Resetting device colors is not yet supported

    def _update_device(self, device):
        """Traverses the states top-down, configuring the devices LEDs accordingly
        
           The states are traversed top-down, registering each of the device's zones that is altered until the 
           end is reached or the entire device is changed by a state. Then the device's new state is set, folowed
           by an update to each of the altered zones. This assures that when a full device's state is removed from the top, 
           individual zone's all get the correct state again.
        
        """
        altered_zones = []
        for state in reversed(self.states):
            device_obj = next((d for d in state["devices"] if d["id"] == device), None)
            if device_obj:
                # If the state alters the entire device's color, use that.
                if "colors" in device_obj or "color" in device_obj:
                    self._set_colors(device, self.client.devices[device])
                    break

                if "zones" in device:
                    altered_zones += [z["id"] for z in device_obj["zones"]]

                # TODO: Individual LEDs
        for zone_id in altered_zones:
            self._update_zone(device, zone_id)

    def _update_zone(self, device, zone):
        """Traverses the states top-down until it finds a state that sets this zone's colors. It then applies those colors"""
        for state in reversed(self.states):
            device_obj = next((d for d in state["devices"] if d["id"] == device), None)
            if device_obj:
                # If the state alters the entire device's color, use that.
                if "colors" in device_obj or "color" in device_obj:
                    self._set_colors(device_obj, self.client.devices[device])
                    break
                pass

                # # Check if the zone itself is altered by this state
                if "zones" in device_obj:
                    zone_obj = next(
                        (z for z in device_obj["zones"] if z["id"] == zone), None
                    )
                    if zone_obj and ("colors" in zone_obj or "color" in zone_obj):
                        self._set_colors(
                            zone_obj, self.client.devices[device].zones[zone]
                        )
                        break

    def _set_colors(self, state_obj, rgb_obj):
        """Updates the device or zone's color when the 'color' or 'colors' key is present in the state"""
        if "colors" in state_obj:
            rgb_obj.set_colors(state_obj["colors"])
        elif "color" in state_obj:
            rgb_obj.set_color(state_obj["color"])


class BaseAction:
    def act(self, context: Context = Context()):
        pass

    def reset(self, context: Context = Context()):
        pass

    def construct_state(self, context: Context):
        return {}


class Action(BaseAction):
    def __init__(self, wrapped_action):
        super().__init__()
        self._inner_action = wrapped_action

    def act(self, context: Context):
        state = self.construct_state(context)
        return context.action_stack.push_state(state)

    def construct_state(self, context: Context):
        state = self._construct_state(context)
        inner_state = self._inner_action.construct_state(context)

        return dict_merge(state, inner_state)

    def _construct_state(self, context: Context):
        return {}

    def reset(self, cookie, context: Context):
        context.action_stack.remove_state(cookie)


class ZoneAction(Action):
    def __init__(
        self,
        wrapped_action: Action,
        zones: TemplatableList,
        leds: TemplatableList = None,
        color: TemplatableList = None,
        colors: Union[List[TemplatableList], str] = None,
        device=None,
        device_type=None,
    ):
        super().__init__(wrapped_action)
        self.zones = list_to_template(zones) if zones else None
        self.leds = list_to_template(leds) if leds else None
        self.color = list_to_template(color) if color else None
        self.colors = [list_to_template(color) for color in colors] if colors else None

        if not color and not colors:
            raise Exception("Either 'color' or 'colors' should be set")
        # TODO: Add option to set modes
        # self.mode = mode
        self.device = device

    def _construct_state(self, context: Context) -> StackState:

        if self.colors:
            color_key = "colors"
            color_val = [color_from_template(c, context) for c in color]
        else:
            color_key = "color"
            color_val = color_from_template(self.color, context)

        zones = [int(x) for x in list_from_template(self.zones, context)]
        state = {
            "devices": [
                {
                    "id": self.device,
                    "zones": [{"id": zone, color_key: color_val} for zone in zones],
                }
            ]
        }
        return state
