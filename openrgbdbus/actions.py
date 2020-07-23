import asyncio
import math
import os
import struct
import time
from colorsys import hls_to_rgb
from typing import List, Union

import numpy as np
import numpy.ma as ma
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
        self.devices = {}
        self.device_animations = {}
        self.device_cookies = {}
        self._initialize()

    def _initialize(self):
        base_state = {"cookie": None, "devices": []}
        for key, device in enumerate(self.client.devices):
            device_state = {"id": key, "colors": device.colors}
            base_state["devices"].append(device_state)
        self.states.append(base_state)
        # TODO: Remove this temp thing
        self.base_state = base_state

        for key, device in enumerate(self.client.devices):
            self.devices[key] = ma.expand_dims(
                self._convert_orgb_state(device.colors), axis=0
            )
            self.devices[key].mask = False
            self.device_cookies[key] = [[]]
            self.device_animations[key] = {}

    def _convert_orgb_state(self, orgb_colors: List[RGBColor]):
        return ma.array([[c.red, c.green, c.blue] for c in orgb_colors]).astype("uint8")

    def current_state(self):
        states = {}
        for key in self.devices:
            states[key] = self.device_state(key)
        return states

    def device_state(self, device: int):
        state = self.devices[device]
        idx = state.shape[0] - state.mask[::-1, :, 1].argmin(axis=0) - 1
        return state[idx, np.arange(state.shape[1])]

    def push_state(self, device, animation: StackState) -> ActionCookie:
        cookie = self._get_cookie()

        # state["cookie"] = cookie
        # state["action"] =
        self.device_cookies[device].append(cookie)
        self.device_animations[device][cookie] = animation
        self.devices[device] = ma.vstack(
            (self.devices[device], np.array(animation(0)[2])[np.newaxis, :, :])
        )

        return cookie

    def remove_state(self, device, cookie: ActionCookie):
        # state = next(
        #     (state for state in self.states if state["cookie"] == cookie), None
        # )
        # self.current_state()
        # if state:
        #     self.states.remove(state)
        #     # Check what devices should be updated
        #     self._update_from_state(state)

        return

        if cookie in self.device_cookies[device]:
            idx = self.device_cookies[device].index(cookie)

            self.devices[device] = np.delete(self.devices[device], idx)
            self.devices[device].mask = False
            del self.device_animations[device][cookie]
            del self.device_cookies[device][idx]

        # self.update()

    async def start_animation_loop(self, frequency=240):
        last_tick = -1
        while True:
            tick = time.monotonic()
            tick_duration = tick - last_tick
            last_tick = tick
            # print(f"Animation TPS: {1 / tick_duration}")

            self.tick_update(tick)
            processing_adjustment = frequency / (1 / tick_duration)
            # await asyncio.sleep(1 / frequency / processing_adjustment)
            await asyncio.sleep(1 / frequency)

    def tick_update(self, timestep: float):
        for device, animations in self.device_animations.items():
            if len(animations) == 0:
                continue

            old_state = self.device_state(device)
            for cookie, animation in animations.items():
                # idx = self.device_cookies[device][cookie]
                idx = self.device_cookies[device].index(cookie)
                # TODO: Zorg dat de animatie niet meer het device hoeft door te geven.
                self.devices[device][idx] = np.array(animation(timestep)[2])
            new_state = self.device_state(device)

            # Update the device if the state has changed
            if (old_state != new_state).any():
                print(f"Updating device {device} (timestep {timestep})")

                colors = [RGBColor(*color) for color in new_state]
                self.client.devices[device].set_colors(colors, fast=True)

    def update_device(self, device):
        """Updates all devices to their current state"""
        state = self.device_state(device)
        colors = [RGBColor(*color) for color in state]
        self.client.devices[device].set_colors(colors, fast=True)

    # def update(self):
    #     """Updates all devices to their current state"""
    #     for device, state in self.current_state().items():
    #         colors = [RGBColor(*color) for color in state]
    #         self.client.devices[device].set_colors(colors)

    def _get_cookie(self):
        """Get a cryptographically secure random cookie
        
           64 bits should be good enough that there's no need the check for duplicate
           ids in the states. (famous last words?)
        """
        return struct.unpack("q", os.urandom(8))

    # def _update_from_state(self, state):
    #     """Updates every device, zone or led that this state effects."""
    #     for device in state["devices"]:
    #         if "zones" in device:
    #             for zone in device["zones"]:
    #                 self._update_zone(device["id"], zone["id"])
    #                 if "leds" in zone:
    #                     for led in zone["leds"]:
    #                         # TODO: (Re)Setting individual LEDs is not yet supported
    #                         pass
    #         if "leds" in device:
    #             for led in device["leds"]:
    #                 # TODO: (Re)Setting individual LEDs is not yet supported
    #                 pass
    #         if "colors" in device or "color" in device:
    #             pass  # TODO: Resetting device colors is not yet supported

    # def _update_device(self, device):
    #     """Traverses the states top-down, configuring the devices LEDs accordingly

    #        The states are traversed top-down, registering each of the device's zones that is altered until the
    #        end is reached or the entire device is changed by a state. Then the device's new state is set, folowed
    #        by an update to each of the altered zones. This assures that when a full device's state is removed from the top,
    #        individual zone's all get the correct state again.

    #     """
    #     altered_zones = []
    #     for state in reversed(self.states):
    #         device_obj = next((d for d in state["devices"] if d["id"] == device), None)
    #         if device_obj:
    #             # If the state alters the entire device's color, use that.
    #             if "colors" in device_obj or "color" in device_obj:
    #                 self._set_colors(device, self.client.devices[device])
    #                 break

    #             if "zones" in device:
    #                 altered_zones += [z["id"] for z in device_obj["zones"]]

    #             # TODO: Individual LEDs
    #     for zone_id in altered_zones:
    #         self._update_zone(device, zone_id)

    # def _update_zone(self, device, zone):
    #     """Traverses the states top-down until it finds a state that sets this zone's colors. It then applies those colors"""
    #     for state in reversed(self.states):
    #         device_obj = next((d for d in state["devices"] if d["id"] == device), None)
    #         if device_obj:
    #             # If the state alters the entire device's color, use that.
    #             if "colors" in device_obj or "color" in device_obj:
    #                 self._set_colors(device_obj, self.client.devices[device])
    #                 break
    #             pass

    #             # # Check if the zone itself is altered by this state
    #             if "zones" in device_obj:
    #                 zone_obj = next(
    #                     (z for z in device_obj["zones"] if z["id"] == zone), None
    #                 )
    #                 if zone_obj and ("colors" in zone_obj or "color" in zone_obj):
    #                     self._set_colors(
    #                         zone_obj, self.client.devices[device].zones[zone]
    #                     )
    #                     break

    # def _set_colors(self, state_obj, rgb_obj):
    #     """Updates the device or zone's color when the 'color' or 'colors' key is present in the state"""
    #     if "colors" in state_obj:
    #         rgb_obj.set_colors(state_obj["colors"])
    #     elif "color" in state_obj:
    #         rgb_obj.set_color(state_obj["color"])


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
        self.animatable = False

    def act(self, context: Context):
        state = self.construct_state(context)
        animation = self.get_animation(context)
        return context.action_stack.push_state(self.device, animation)

    def construct_state(self, context: Context):
        state = self._construct_state(context)
        inner_state = self._inner_action.construct_state(context)

        return dict_merge(state, inner_state)

    def _construct_state(self, context: Context):
        return {}

    def reset(self, cookie, context: Context):
        context.action_stack.remove_state(self.device, cookie)


class AnimatableAction(Action):
    def __init__(
        self,
        wrapped_action: Action,
        zones: TemplatableList,
        leds: TemplatableList = None,
        color: TemplatableList = None,
        device=None,
        device_type=None,
    ):
        super().__init__(wrapped_action)
        self.zones = list_to_template(zones) if zones else None
        self.leds = list_to_template(leds) if leds else None
        self.color = list_to_template(color) if color else None

        if not color:
            raise Exception("'color' should be set")
        # TODO: Add option to set modes
        # self.mode = mode
        self.device = device
        self.animatable = True

    def get_animation(self, context: Context) -> StackState:
        device = self.device
        c_device = context.rgb_client.devices[self.device]
        # TODO: Handle this properly
        leds = self.zones
        color_template = ma.masked_all((len(c_device.colors), 3)).astype("uint8")
        # led_count = len(leds)

        speed = 20
        hue_distribution = 0

        def animate(timestep: float):
            scaled_time = timestep * speed

            for i, led in enumerate(leds):
                offset = i / len(leds) * hue_distribution
                offset *= 255
                # offset = i / (1 + len(leds) * hue_distribution) * 255
                hue = (scaled_time + offset) % 255
                color_template[led] = np.array(hls_to_rgb(hue / 255, 0.5, 1)) * 255

            # color_template[leds] = (
            #     (np.asarray([color]) * 255).astype("uint8").repeat(len(leds), axis=0)
            # )
            print(color_template[0])
            return device, leds, color_template

        return animate


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
