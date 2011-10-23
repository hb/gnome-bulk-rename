# GNOME bulk rename utility
# Copyright (C) 2010-2011 Holger Berndt <hb@gnome.org>
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA

"""Registration with file managers."""

from gi.repository import GLib
from gi.repository import Gio

import config
import constants


def startup_check_file_managers(logger):
    """Dealing with file managers on startup.
    
    Check if somebody is registered. If not, register this tool."""
    classes = [_Nautilus]
    for cl in classes:
        try:
            inst = cl()
            setting = inst.get_bulk_renamer_setting().strip()
            if setting == "":
                inst.register()
                logger.info("Registered on %s" % cl)
            elif config.appname not in setting:
                logger.info("Didn't register on %s - another command already registered: '%s'" % (cl, setting))
            else:
                logger.info("Already registered as '%s'" % setting)
        except RuntimeError:
            logger.info("Startup registration for %s skipped." % cl)


def _get_setting_string():
    return config.appname + " -s"


#TODO: this is just here to work around bystring bug in pygobject
def _get_str_from_variant_bytestring(var):
    return "".join([chr(el) for el in var.unpack()])[:-1]


class _Nautilus(object):
    
    def __init__(self):
        
        # Check for Nautilus' schema
        schemas = Gio.Settings.list_schemas()
        if constants.SETTINGS_SCHEMA_NAUTILUS not in schemas:
            raise RuntimeError("Nautilus schema not found.")
        
        self._settings = Gio.Settings(schema=constants.SETTINGS_SCHEMA_NAUTILUS)
    
    
    def get_bulk_renamer_setting(self):
        if constants.SETTINGS_NAUTILUS_BULK_RENAME_TOOL not in self._settings.list_keys():
            return None

        val = GLib.Variant.new_bytestring(_get_setting_string())
        val = self._settings.get_value(constants.SETTINGS_NAUTILUS_BULK_RENAME_TOOL)
        return _get_str_from_variant_bytestring(val)

    def register(self):
        if constants.SETTINGS_NAUTILUS_BULK_RENAME_TOOL in self._settings.list_keys():
            # TODO: pygobject bytestring variants seem unstable
            val = GLib.Variant("ay", _get_setting_string() + chr(0))
            self._settings.set_value(constants.SETTINGS_NAUTILUS_BULK_RENAME_TOOL, val)
