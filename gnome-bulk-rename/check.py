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

"""Various checks"""


from gi.repository import Gtk
from gi.repository import Gio
from gi.repository import GLib

import constants


class Checker:
    """Perform various checks on a model"""

    def __init__(self, model):
        # results that can be queried
        self.all_names_stay_the_same = True
        self.highest_problem_level = 0
        self.circular_uris = set()

        # common data
        self._model = model


    def clear_all_warnings_and_errors(self):
        for row in self._model:
            row[constants.FILES_MODEL_COLUMN_ICON_STOCK] = ""
            row[constants.FILES_MODEL_COLUMN_TOOLTIP] = GLib.markup_escape_text(row[constants.FILES_MODEL_COLUMN_GFILE].get_uri())


    def perform_checks(self):
        """Run tests. Clears the model first."""
        self.clear_all_warnings_and_errors()

        self._check_if_all_names_stay_the_same()
        
        # there can't be any problems in this case
        if not self.all_names_stay_the_same:
            # more common data
            self._list_of_source_uris = [(row[constants.FILES_MODEL_COLUMN_URI_DIRNAME] + row[0]) for row in self._model]
            self._list_of_target_uris = [(row[constants.FILES_MODEL_COLUMN_URI_DIRNAME] + row[1]) for row in self._model]

            self._dict_source_uri_to_index = {}
            for ii, uri in enumerate(self._list_of_source_uris):
                self._dict_source_uri_to_index[uri] = ii

            self._dict_target_uri_to_indices = {}
            for ii, uri in enumerate(self._list_of_target_uris):
                self._dict_target_uri_to_indices.setdefault(uri, []).append(ii)                    
            
            # checks
            self._check_for_empty_targets()
            self._check_slash_in_target()
            self._check_for_double_targets()
            self._check_for_circular_renaming()
            self._check_for_already_existing_names()


    def _check_if_all_names_stay_the_same(self):
        self.all_names_stay_the_same = True
        for row in self._model:
            if row[0] != row[1]:
                self.all_names_stay_the_same = False


    def _check_for_empty_targets(self):
        msg = "<b>%s:</b> %s" % (_("ERROR"), _("Empty target name"))
        for ii,row in enumerate(self._model):
            if row[1] == "":
                self._model[ii][constants.FILES_MODEL_COLUMN_ICON_STOCK] = Gtk.STOCK_DIALOG_ERROR
                self.highest_problem_level = max(self.highest_problem_level, 2)
                self._add_tooltip_msg(ii, msg)
                
    def _check_slash_in_target(self):
        msg = "<b>%s:</b> %s" % (_("ERROR"), _("Slash in target name"))
        for ii,row in enumerate(self._model):
            if "/" in row[1]:
                self._model[ii][constants.FILES_MODEL_COLUMN_ICON_STOCK] = Gtk.STOCK_DIALOG_ERROR
                self.highest_problem_level = max(self.highest_problem_level, 2)
                self._add_tooltip_msg(ii, msg)
        
                    
    def _check_for_double_targets(self):
        """Sets pixbuf and tooltip text. Returns True if double targets exist"""
        double_uris = []
        for key,value in self._dict_target_uri_to_indices.items():
            if len(value) > 1:
                double_uris.append(key)

        msg = "<b>%s:</b> %s" % (_("ERROR"), _("Double output filepath"))
        registered = set()
        for uri in double_uris:
            for ii in self._dict_target_uri_to_indices[uri]:
                if ii not in registered:
                    self._model[ii][constants.FILES_MODEL_COLUMN_ICON_STOCK] = Gtk.STOCK_DIALOG_ERROR
                    self.highest_problem_level = max(self.highest_problem_level, 2)
                    self._add_tooltip_msg(ii, msg)
                    registered.add(ii)


    def _check_for_circular_renaming(self):
        self.circular_uris = set()
        # we have a circular renaming if one row's source refers to the same uri as another row's target
        set_of_source_uris = set(self._list_of_source_uris)
        set_of_target_uris = set(self._list_of_target_uris)
        possible_circular_uris = set_of_source_uris.intersection(set_of_target_uris)
        for pu in possible_circular_uris:
            if len(self._dict_target_uri_to_indices[pu]) > 1 or self._dict_source_uri_to_index[pu] != self._dict_target_uri_to_indices[pu][0]:
                self.circular_uris.add(pu)


    def _check_for_already_existing_names(self):
        """Check if a target name already exists on the file system, but is not a circular rename"""
        existing_files = set()
        for row in self._model:
            if row[0] == row[1] or not row[1]:
                continue
            new_name = row[constants.FILES_MODEL_COLUMN_URI_DIRNAME] + row[1]
            if new_name not in self.circular_uris:
                parent = Gio.file_new_for_uri(row[constants.FILES_MODEL_COLUMN_URI_DIRNAME])
                file = parent.get_child_for_display_name(row[1])
                if file.query_exists(None):
                    existing_files.add(new_name)

        # mark files
        msg = "<b>%s:</b> %s" % (_("WARNING"), _("Target filename already exists on the filesystem"))
        for uri in existing_files:
            for idx in self._dict_target_uri_to_indices[uri]:
                if self._model[idx][constants.FILES_MODEL_COLUMN_ICON_STOCK] != Gtk.STOCK_DIALOG_ERROR:
                    self._model[idx][constants.FILES_MODEL_COLUMN_ICON_STOCK] = Gtk.STOCK_DIALOG_WARNING
                self._add_tooltip_msg(idx, msg)
                self.highest_problem_level = max(self.highest_problem_level, 1)


    def _add_tooltip_msg(self, row_num, msg):
        self._model[row_num][constants.FILES_MODEL_COLUMN_TOOLTIP] = self._model[row_num][constants.FILES_MODEL_COLUMN_TOOLTIP] + "\n" + msg
