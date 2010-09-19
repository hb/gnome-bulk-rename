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

"""Preview-like objects need to implement the "preview" function and have
a "short_description" class member. If it also has a "skip" class member
which evaluates to True, the class is skipped. Optionally, a class may also
set a priority class member, which affects the sorting order in the combo box.
If not given, a value of 0.5 is assumed.

The constructor needs to take a refresh func as argument, which must not
be called during preview (or an endless loop might occur). Also, it should
only be called when the current preview configuration is sensible.
The second argument is a function to be called when the preview class'
configuration is currently invalid.

After construction, the preview class is supposed to be in a valid state."""

import string


class PreviewNoop(object):
    """Source name is identical to target name."""

    short_description = "No change"
    skip = False
    priority = 0.1

    def __init__(self, refresh_func, invalid_func):
        pass
        
    def preview(self, model):
        for row in model:
            row[1] = row[0]


class PreviewTranslate(object):
    """General character translation"""

    short_description = "Character translation"
    skip = True

    def __init__(self, refresh_func, invalid_func):
        self._translation_table = None

    def set_source_and_target(self, source, target):
        self._translation_table = string.maketrans(source, target)
    
    def preview(self, model):
        if self._translation_table:
            for row in model:
                row[1] = row[0].translate(self._translation_table)



class PreviewReplaceSpacesWithUnderscores(PreviewTranslate):

    short_description =  "Replace spaces with underscores"
    skip = False
    priority = 0.4
    
    def __init__(self, refresh_func, invalid_func):
        PreviewTranslate.__init__(self, refresh_func, invalid_func)
        self.set_source_and_target(" ", "_")


class PreviewReplaceEverySecondWithFixedString(object):
    """Just for testing"""
    
    short_description = "Replace with fixed string"
    skip = False
    priority = 0.8
    
    def __init__(self, refresh_func, invalid_func):
        pass
    
    def preview(self, model):
        for ii,row in enumerate(model):
            if (ii % 2) == 0:
                row[1] = "foobar"
            else:
                row[1] = row[0]


class PreviewCircleNames(object):
    """Just for testing"""

    short_description = "Circle names"
    skip = False
    priority = 0.81
    
    def __init__(self, refresh_func, invalid_func):
        pass

    def preview(self, model):
        if not model:
            return
        for ii in range(1, len(model)):
            model[ii-1][1] = model[ii][0]
        model[len(model)-1][1] = model[0][0]



class PreviewToggleSpaceUnderscore(PreviewTranslate):
    
    short_description = "Toggle space underscore"
    skip = False
    ct = 0
    
    def __init__(self, refresh_func, invalid_func):
        pass
    
    def preview(self, model):
        if (PreviewToggleSpaceUnderscore.ct % 2) == 0:
            self.set_source_and_target(" ", "_")
        else:
            self.set_source_and_target("_", " ")
        PreviewTranslate.preview(self, model)
        PreviewToggleSpaceUnderscore.ct += 1
            