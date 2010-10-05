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

"""Sorting of the files model"""

import pygtk
pygtk.require('2.0')
from gi.repository import Gtk

from gettext import gettext as _

import constants

class Manually(object):
    description = _("No automatic sorting is applied to the files. It is possible to rearrange the files by drag and drop.")

class ByName(object):
    
    # TRANSLATORS: This string is used in a selection for sorting
    short_description = _("by name")
    priority = 0.2
    description = _("Sort the files by their current file name.")

    def __init__(self, treesortable):
        self._treesortable = treesortable

        case_check = Gtk.CheckButton(label=_("Case insensitive"))
        case_check.set_active(False)
        case_check.connect("toggled", self._on_case_check_toggled)
        self._config_widget = case_check
        
        self._case_sensitive = True


    def sort(self, model, iter1, iter2, user_data):
        if self._case_sensitive:
            return cmp(model.get_value(iter1, 0), model.get_value(iter2, 0))
        else:
            return cmp(model.get_value(iter1, 0).lower(), model.get_value(iter2, 0).lower())


    def get_config_widget(self):
        return self._config_widget


    def _on_case_check_toggled(self, checkbutton):
        self._case_sensitive = not checkbutton.get_active()

        # trigger re-sort
        old_id_and_order = self._treesortable.get_sort_column_id()
#HHBTODO Gtk.TREE_SORTABLE_UNSORTED_SORT_COLUMN_ID auf -2 gesetzt 
        self._treesortable.set_sort_column_id(-2, Gtk.SortType.DESCENDING)
        self._treesortable.set_sort_column_id(*old_id_and_order)
