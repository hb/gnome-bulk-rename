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

class RenameUndoAction(object):
    def __init__(self, model):
        raise NotImplementedError


class UndoStack(object):
    """Undo stack for undo-like objects.

    Undo-like objects need to implement the undo and redo member functions."""

    def __init__(self):
        self._undo_stack = []
        self._redo_stack = []

    def push(self, action):
        """Action must be an undo-like object"""
        self._stack.append(action)
        self._redo_stack = []

    def undo(self):
        action = self._undo_stack.pop()
        success = action.undo()
        if success:
            self._redo_stack.append(action)
        return success

    def redo(self):
        action = self._redo_stack.pop()
        success = action.redo()
        if success:
            self._undo_stack.append(action)
        return success