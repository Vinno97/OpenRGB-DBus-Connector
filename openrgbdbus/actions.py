from typing import List

import numpy as np
from openrgb.utils import DeviceType, RGBColor

from .utils import Context


class BaseAction:
    def act(self, context: Context = Context()):
        pass

    def reset(self, context: Context = Context()):
        pass


class NoopAction(BaseAction):
    def __init__(self):
        super().__init__()

    def act(self, context: Context = Context()):
        if context.debug:
            print("(%s): Act!" % id(self))

    def reset(self, context: Context = Context()):
        if context.debug:
            print("(%s): Reset!" % id(self))


class Action(BaseAction):
    def __init__(self, wrapped_action):
        super().__init__()
        self._inner_action = wrapped_action

    def act(self, context: Context):
        self._act(context)
        self._inner_action.act(context)

    def reset(self, context: Context):
        self._reset(context)
        self._inner_action.reset(context)

    def _act(self, context: Context):
        pass

    def _reset(self, context: Context):
        pass


class ZoneAction(Action):
    def __init__(
        self,
        wrapped_action: Action,
        zones: List[int],
        color: List[int] = None,
        colors: List[List[int]] = None,
        device=None,
        device_type=None,
    ):
        super().__init__(wrapped_action)
        self.zones = zones
        self.color = color
        self.colors = color
        if self.color is None and self.colors is None:
            raise Exception("Either 'color' or 'colors' should be set")
        # TODO: Add option to set modes
        # self.mode = mode
        self.device = device
        self.previous_colors = None

    def _act(self, context: Context = Context()):
        client = context.rgb_client
        device = client.devices[self.device]
        zones = [zone for zone in device.zones if zone.id in self.zones]
        self.previous_colors = [zone.colors for zone in zones]
        for zone in zones:
            if self.color:
                zone.set_color(RGBColor(*self.color))
            else:
                zone.set_colors([RGBColor(*color) for color in self.colors])

    def _reset(self, context: Context = Context()):
        client = context.rgb_client
        device = client.devices[self.device]
        for zone in self.zones:
            device.zones[zone].set_colors(self.previous_colors[zone])
