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

"""Markup changes between old and new names.
Markup-like objects need to implement the markup member function."""

import difflib

from gi.repository import GLib

import constants


class MarkupNoop(object):
    """No additional markup"""
    
    short_description = _("No markup")
    priority = 0.1
    
    @staticmethod
    def markup(model):
        for row in model:
            row[constants.FILES_MODEL_COLUMN_MARKUP_ORIGINAL] = GLib.markup_escape_text(row[constants.FILES_MODEL_COLUMN_ORIGINAL])
            row[constants.FILES_MODEL_COLUMN_MARKUP_PREVIEW] = GLib.markup_escape_text(row[constants.FILES_MODEL_COLUMN_PREVIEW])


class MarkupColor(object):
    """Colored markup"""
    
    short_description = _("Colored markup")
    default = True
    priority = 0.2
    
    def __init__(self, delete_color="LightSalmon1", insert_color="Palegreen1", replace_color="LightSkyBlue1"):
        self._matcher = difflib.SequenceMatcher()
        
        self._marker_delete_start = "<span bgcolor='{0}'>".format(delete_color)
        self._marker_delete_end = "</span>"
        self._marker_insert_start = "<span bgcolor='{0}'>".format(insert_color)
        self._marker_insert_end = "</span>"
        self._marker_replace_start = "<span bgcolor='{0}'>".format(replace_color)
        self._marker_replace_end = "</span>"


    def markup(self, model):
        for row in model:
            oldstring = GLib.markup_escape_text(row[constants.FILES_MODEL_COLUMN_ORIGINAL])
            newstring = GLib.markup_escape_text(row[constants.FILES_MODEL_COLUMN_PREVIEW])
            oldlist = []
            newlist = []
            self._matcher.set_seqs(oldstring, newstring)
            for (tag, i1, i2, j1, j2) in self._matcher.get_opcodes():
                if tag == "equal":
                    oldlist.append(oldstring[i1:i2])
                    newlist.append(newstring[j1:j2])
                elif tag == "delete":
                    oldlist.extend([self._marker_delete_start, oldstring[i1:i2], self._marker_delete_end])
                elif tag == "replace":
                    oldlist.extend([self._marker_replace_start, oldstring[i1:i2], self._marker_replace_end])
                    newlist.extend([self._marker_replace_start, newstring[j1:j2], self._marker_replace_end])
                elif tag == "insert":
                    newlist.extend([self._marker_insert_start, newstring[j1:j2], self._marker_insert_end])

            row[constants.FILES_MODEL_COLUMN_MARKUP_ORIGINAL] = "".join(oldlist)
            row[constants.FILES_MODEL_COLUMN_MARKUP_PREVIEW] = "".join(newlist)
