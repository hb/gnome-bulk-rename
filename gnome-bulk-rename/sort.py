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

"""Sorting of the files model"""

import pygtk
pygtk.require('2.0')
import gtk


class ByName(object):
    
    short_description = "by name"
    
    def __init__(self, treesortable):
        self._treesortable = treesortable

        case_check = gtk.CheckButton("Case sensitive")
        case_check.set_active(True)
        case_check.connect("toggled", self._on_case_check_toggled)
        self._config_widget = case_check
        
        self._case_sensitive = True


    def sort(self, model, iter1, iter2):
        if self._case_sensitive:
            return cmp(model.get(iter1, 0)[0], model.get(iter2, 0)[0])
        else:
            return cmp(model.get(iter1, 0)[0].lower(), model.get(iter2, 0)[0].lower())


    def get_config_widget(self):
        return self._config_widget


    def _on_case_check_toggled(self, checkbutton):
        self._case_sensitive = checkbutton.get_active()

        # trigger re-sort
        old_id_and_order = self._treesortable.get_sort_column_id()
        self._treesortable.set_sort_column_id(gtk.TREE_SORTABLE_UNSORTED_SORT_COLUMN_ID, gtk.SORT_DESCENDING)
        self._treesortable.set_sort_column_id(*old_id_and_order)
