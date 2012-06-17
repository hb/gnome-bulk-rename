# GNOME bulk rename utility
# Copyright (C) 2010-2012 Holger Berndt <hb@gnome.org>
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

from gi.repository import Gtk

from gettext import gettext as _

import constants
import utils

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
        self._case_check = case_check
        self._config_widget = case_check
        
        self._case_sensitive = True


    def sort(self, model, iter1, iter2, user_data):
        if self._case_sensitive:
            return utils.cmp(model.get_value(iter1, 0), model.get_value(iter2, 0))
        else:
            return utils.cmp(model.get_value(iter1, 0).lower(), model.get_value(iter2, 0).lower())


    def get_config_widget(self):
        return self._config_widget

    
    def get_state(self):
        state = {}
        state["case_check"] = self._case_check.get_active()
        return state

    
    def restore_state(self, state):
        if "case_check" in state:
            self._case_check.set_active(state["case_check"])


    def _on_case_check_toggled(self, checkbutton):
        self._case_sensitive = not checkbutton.get_active()

        # trigger re-sort
        old_id_and_order = self._treesortable.get_sort_column_id()
        self._treesortable.set_sort_column_id(constants.GBR_GTK_TREE_SORTABLE_UNSORTED_SORT_COLUMN_ID, Gtk.SortType.DESCENDING)
        if old_id_and_order[0] is not None:
            self._treesortable.set_sort_column_id(*old_id_and_order)
