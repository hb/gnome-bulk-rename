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

"""Markup changes between old and new names.
Markup-like objects need to implement the markup member function."""

import difflib
import constants

class MarkupNoop(object):
    """No additional markup"""
    @staticmethod
    def markup(model):
        for row in model:
            row[constants.FILES_MODEL_COLUMN_MARKUP_ORIGINAL] = row[constants.FILES_MODEL_COLUMN_ORIGINAL]
            row[constants.FILES_MODEL_COLUMN_MARKUP_PREVIEW] = row[constants.FILES_MODEL_COLUMN_PREVIEW]


class MarkupColor(object):
    """Colored markup"""
    
    def __init__(self):
        self._matcher = difflib.SequenceMatcher()
        self._marker_delete_start = "<span bgcolor='LightSalmon1'>"
        self._marker_delete_end = "</span>"
        self._marker_insert_start = "<span bgcolor='Palegreen1'>"
        self._marker_insert_end = "</span>"
        self._marker_replace_start = "<span bgcolor='LightSkyBlue1'>"
        self._marker_replace_end = "</span>"
        
    
    def markup(self, model):
        for row in model:
            oldstring = row[constants.FILES_MODEL_COLUMN_ORIGINAL]
            newstring = row[constants.FILES_MODEL_COLUMN_PREVIEW]
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
