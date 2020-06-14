# D-Bus Connector for OpenRGB

**Currently refractoring and migrating from [B. Horn's OpenRGB Client](https://github.com/bahorn/OpenRGB-PyClient) to [Jath03's openrgb-python](https://github.com/jath03) library. Last working commit is 37565898b9721d13ab537a44c016efdb02f7005e**.

## What is this project?

This project offers an easy™ way to have you PC's lighting effects respond to events on your PC. Most, if not all, modern Linux-based desktops use D-Bus to share information between applications. This tool listens for designated signals on this bus and can change lighting effects when an event is detected.

It is built for, and relies upon, the recently released  OpenRGB SDK, which is part of the amazing [OpenRGB](https://gitlab.com/CalcProgrammer1/OpenRGB) project.


## How it works

The tool works by listening to the D-Bus system until it receives a signal that matches its filters. It can then optionally perform certain additional checks via the D-Bus system before it decides an task should be executed. This task consists out of one or more changes to the PC's lights. At the same time, it also starts listening for a second signal that indicates the event is 'done' and the changes in lighting should be reversed (this last part is currently not implemented, see '[TODO](#todo)').

The entire configuration of the tool is defined in the `hooks.yaml`, which is constructed as follows:

```yaml
version: <version number for config format>

server: # Optional way to specify the location of the OpenRGB SDK
  host: <host where the OpenRGB SDK is running. Defaults to 'localhost'>
  port: <port that the OpenRGB SDK is attached to. Defaults to 1337>

debug: <optional boolean flag to enable debug logging, defaults to false> 

default: # Optional list of actions to run when the program is started.  
  - device_id: <numerical id of device controller>
    zones: <list of affected leds>
    color: <list of 0-255 for R, G and B values>

hooks:
    [hook_name]:
        bus: <d-bus name | default: 'session'> 
        action: <action> 
            # What to do when the hook is triggered (single action). See the usage
            # see "default" for how an action should be defined.
        actions: # Can be used instead of 'action' do define multiple actions.
            - <action>
            - <action>
            - ...
        trigger: # Defines when the hook is triggered
            signal: # Filters what signal(s) should trigger the hook
                path: <D-Bus object path>
                interface: <D-Bus interface>
                name: <D-Bus member name>
                arguments: <list of strings for the signal arguments to be checked against>
            conditions: # Optional extra checks to execute when a signal is received
                - service_name: <name of service on the bus>
                  path: <D-Bus object path>
                  method: <D-Bus member name of method to call>
                  response: <Expected response>
        until:
            signal: # Same as trigger.signal
            conditions: # Same as trigger.conditions

```

Example configurations can be found in `./examples`.

**Note:** The D-Bus handling is fairly sophisticated, but the lighting controls are still severely lacking. The color of every LED of every device (exposed by OpenRGB) can be changed. There is currently no way to revert those changes when the event has finished. This would require the program to read and save the state of the LEDs before overwriting them. Though this can be easily added due to the way the actions are implemented, I have not yet gotten around to figuring out how to get this information from OpenRGB.


This project is still in its very early stages and should not be viewed as a finished product. The code is architectually sound, but the file structure follows the "I need it here, so I write it here"-ideology.

## TODO

* [x] Add conditional value checks for arguments (evaluate response of D-Bus methods after signal is received).
* [x] Reset lights to their original state after event has passed.
* [ ] Make `until` hooks optional (for one-shot hooks)
* [ ] Add timed hooks (Stop effect after delay instead of waiting for a stopping trigger).
* [x] Add zone control.
* [ ] Make optional D-Bus properties for signals and conditions actually optional.
* [ ] Extend conditional checks to support methods that return non-string responses (ints, arrays, objects, etc.). 
* [ ] Allow for easier configuration (no hard-coded config, multiple files, etc.).
* [ ] Add support for controlling animations/modes.
* [x] Clean file structure.
* [ ] Write proper documentation.
* [ ] Write more example configurations.
* [x] Allow the OpenRGB server port to be changed.
* [ ] Allow loading of profiles (how should these be reset?)
* [ ] Implement more advanced templating ([Jinja?](http://zetcode.com/python/jinja/)).


## Special thanks to

* [Adam Honse](https://gitlab.com/CalcProgrammer1), for developing OpenRGB
* [jath03](https://github.com/jath03), for developing [openrgb-python](https://github.com/jath03/openrgb-python), which is used to interface with the OpenRGB SDK.
* [B. Horn](https://github.com/bahorn), for developing the [OpenRGB Python Client](https://github.com/bahorn/OpenRGB-PyClient). The first versions of this program ran on this library. Without it, I would probably have dropped the idea for this project in its early stages.
* [Matt Harper](https://gitlab.com/matt.harper), for implementing RGB Fusion 2 support in OpenRGB, allowing me to use it for my own PC.
* All the other contributors to the [OpenRGB](https://gitlab.com/CalcProgrammer1/OpenRGB).
* Of course the [D-Bus](https://www.freedesktop.org/wiki/Software/dbus/) project, for being the backbone of my desktop and enabling this project to listen to its messages.
