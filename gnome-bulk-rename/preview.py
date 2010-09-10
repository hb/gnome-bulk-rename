#!/usr/bin/env python

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

"""Preview-like objects need to implement the "preview" member function.
The constructor needs to take a refresh func as argument, which must not
be called during preview (or an endless loop might occur)."""

import string


class PreviewNoop(object):
    """Source name is identical to target name."""
    def __init__(self, refresh_func):
        self._refresh_func = refresh_func

    def preview(model):
        for row in model:
            row[1] = row[0]


class PreviewTranslate(object):
    """Character translations"""
    def __init__(self, refresh_func, source=None, target=None):
        self._refresh_func = refresh_func
        self._translation_table = None
        if source and target:
            self.set_source_and_target(source, target)

    def preview(self, model):
        if self._translation_table:
            for row in model:
                row[1] = row[0].translate(self._translation_table)
    
    def set_source_and_target(self, source, target):
        self._translation_table = string.maketrans(source, target)    
