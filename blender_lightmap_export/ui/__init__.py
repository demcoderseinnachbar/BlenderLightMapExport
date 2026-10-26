# SPDX-License-Identifier: GPL-3.0-or-later
"""Blender user interface (registered only when running as an add-on)."""


def register():
    from . import properties, operators, panels, preferences
    preferences.register()
    properties.register()
    operators.register()
    panels.register()


def unregister():
    from . import properties, operators, panels, preferences
    panels.unregister()
    operators.unregister()
    properties.unregister()
    preferences.unregister()
