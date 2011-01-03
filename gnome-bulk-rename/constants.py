# GNOME bulk rename utility
# Copyright (C) 2010 Holger Berndt <hb@gnome.org>
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

"""Various constants"""

import pygtk
pygtk.require("2.0")
from gi.repository import Gio

FILES_MODEL_COLUMNS = (str, str, Gio.File, str, str, str, str, str)
FILES_MODEL_COLUMN_ORIGINAL = 0         # code relies on that
FILES_MODEL_COLUMN_PREVIEW = 1          # code relies on that
FILES_MODEL_COLUMN_GFILE = 2            # code relies on that
FILES_MODEL_COLUMN_MARKUP_ORIGINAL = 3
FILES_MODEL_COLUMN_MARKUP_PREVIEW = 4
FILES_MODEL_COLUMN_ICON_STOCK = 5
FILES_MODEL_COLUMN_TOOLTIP = 6
FILES_MODEL_COLUMN_URI_DIRNAME = 7
    
EXTENSIBLE_MODEL_COLUMNS = (str, object, float, bool, str)
EXTENSIBLE_MODEL_COLUMN_SHORT_DESCRIPTION = 0
EXTENSIBLE_MODEL_COLUMN_OBJECT = 1
EXTENSIBLE_MODEL_COLUMN_PRIORITY = 2
EXTENSIBLE_MODEL_COLUMN_VISIBLE = 3
EXTENSIBLE_MODEL_COLUMN_SHORT_DESCRIPTION_MARKUP = 4

SORT_ID_MANUAL = 0

FILES_INFO_BAR_RESPONSE_ID_INFO_WARNING = 1
FILES_INFO_BAR_RESPONSE_ID_INFO_ERROR = 2
FILES_INFO_BAR_RESPONSE_ID_UNDO = 3

SETTINGS_SCHEMA_NAUTILUS = "org.gnome.nautilus.preferences"
SETTINGS_NAUTILUS_BULK_RENAME_TOOL = "bulk-rename-tool"