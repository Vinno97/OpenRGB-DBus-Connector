from typing import List

import numpy as np


class BaseAction:
    def __init__(self, client):
        self._client = client

    @property
    def client(self):
        return self._client

    @client.setter
    def client(self, client):
        self._client = client

    def act(self, config):
        for device, cmap in config.items():
            self.client.update_leds(cmap, device_id=device)

    def reset(self, config):
        for device, cmap in config.items():
            self.client.update_leds(cmap, device_id=device)


class NoopAction(BaseAction):
    def __init__(self, debug=True):
        super().__init__(None)
        self.debug = debug

    def act(self, config):
        if self.debug:
            print("(%s): Act!" % id(self))
        super().act(config)

    def reset(self, config):
        if self.debug:
            print("(%s): Reset!" % id(self))


class Action(BaseAction):
    def __init__(self, wrapped_action, client=None):
        client = client if client else wrapped_action.client
        super().__init__(client)
        self._inner_action = wrapped_action

    @property
    def client(self):
        return self._inner_action.client

    @client.setter
    def client(self, client):
        self._inner_action.client = client

    def act(self, config={}):
        self._act(config)
        self._inner_action.act(config)

    def reset(self, config={}):
        self._reset(config)
        self._inner_action._reset(config)

    def _act(self, config):
        pass

    def _reset(self, config):
        pass


class LedAction(Action):
    def __init__(
        self,
        device: int,
        leds: List[int],
        color: List[int],
        wrapped_action,
        client=None,
    ):
        super().__init__(wrapped_action, client)
        self._inner_action = wrapped_action
        self.device = device
        self.leds = leds
        self.color = color

    # TODO Move this functionaility to a place where the current state can be saved in the config
    def set_up_config(self, config):
        led_count = len(self.client.controller_data(
            device_id=self.device).leds)
        color_dims = 3
        return np.zeros((led_count, color_dims), dtype=np.ubyte)

    def _act(self, config):
        if not self.device in config:
            config[self.device] = self.set_up_config(config)
        config[self.device][self.leds] = [self.color] * len(self.leds)
