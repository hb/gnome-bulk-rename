# Copyright (C) 2010 Holger Berndt <hb@gnome.org>
# 
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the
# License, or (at your option) any later version.
#  
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public
# License along with this program; if not, write to the
# Free Software Foundation, Inc., 59 Temple Place - Suite 330,
# Boston, MA 02111-1307, USA.

"""Various constants"""

__version__ = "0.0.1"

application_name = "gnome-bulk-rename"

FILES_MODEL_COLUMNS = (str, str, str, str, object, str, str, str)
FILES_MODEL_COLUMN_ORIGINAL = 0         # code relies on that
FILES_MODEL_COLUMN_PREVIEW = 1          # code relies on that
FILES_MODEL_COLUMN_MARKUP_ORIGINAL = 2
FILES_MODEL_COLUMN_MARKUP_PREVIEW = 3
FILES_MODEL_COLUMN_GFILE = 4
FILES_MODEL_COLUMN_ICON_STOCK = 5
FILES_MODEL_COLUMN_TOOLTIP = 6
FILES_MODEL_COLUMN_URI_DIRNAME = 7
    
PREVIEWS_SELECTION_COLUMNS = (str, object, float)
PREVIEWS_SELECTION_DESCRIPTION = 0
PREVIEWS_SELECTION_PREVIEW = 1
PREVIEWS_SELECTION_PRIORITY = 2

SORTING_COLUMNS = (str, int, object)
SORTING_COLUMN_TEXT = 0
SORTING_COLUMN_ID = 1
SORTING_COLUMN_INSTANCE = 2

SORT_ID_MANUAL = 0

FILES_INFO_BAR_RESPONSE_ID_INFO_WARNING = 1
FILES_INFO_BAR_RESPONSE_ID_INFO_ERROR = 2
FILES_INFO_BAR_RESPONSE_ID_UNDO = 3
