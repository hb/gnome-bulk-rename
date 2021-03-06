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

from gi.repository import GObject
from gi.repository import Gtk


class Undo(GObject.GObject):
    """Undo stack for undo-like objects.

    Undo-like objects need to implement the undo and redo member functions.
    It doesn't transfer undo objects directly to the redo stack, because
    they are async, and when undo() returns, it's not yet clear if it
    should go to the redo stack or not."""

    UNDO_ACTION_NAME = "undoundoactionname"
    REDO_ACTION_NAME = "undoredoactionname"

    __gsignals__ = {
        "can-undo" : (GObject.SignalFlags.RUN_LAST, None,
                      (GObject.TYPE_BOOLEAN,)),
        "can-redo" : (GObject.SignalFlags.RUN_LAST, None,
                      (GObject.TYPE_BOOLEAN,)),
        }

    def __init__(self):
        GObject.GObject.__init__(self)

        # stacks
        self._undo_stack = []
        self._redo_stack = []

        # actions
        self._undo_action = Gtk.Action.new(Undo.UNDO_ACTION_NAME, "Undo", None, Gtk.STOCK_UNDO)
        self._undo_action.set_sensitive(False)
        self._undo_action.connect("activate", lambda action, undo : undo(), self.undo)

        self._redo_action = Gtk.Action.new(Undo.REDO_ACTION_NAME, "Redo", None, Gtk.STOCK_REDO)
        self._redo_action.set_sensitive(False)
        self._redo_action.connect("activate", lambda action, redo : redo(), self.redo)


    def get_undo_action(self):
        return self._undo_action

    def get_redo_action(self):
        return self._redo_action


    def push(self, action):
        """Action must be an undo-like object"""
        had_redo_stack = (len(self._redo_stack) > 0)
        self._redo_stack = []
        self.push_back_to_undo(action)
        if had_redo_stack:
            self._changed_can_redo(False)
        

    def push_to_redo(self, action):
        self._redo_stack.append(action)

        if len(self._redo_stack) == 1:
            self._changed_can_redo(True)

    
    def push_back_to_undo(self, action):
        self._undo_stack.append(action)

        if len(self._undo_stack) == 1:
            self._changed_can_undo(True)


    def undo(self):
        action = self._undo_stack.pop()
        action.undo()

        if not self._undo_stack:
            self._changed_can_undo(False)
            

    def redo(self):
        action = self._redo_stack.pop()
        action.redo()

        if not self._redo_stack:
            self._changed_can_redo(False)

            
    def _changed_can_undo(self, can_undo):
        self.emit("can-undo", can_undo)
        self._undo_action.set_sensitive(can_undo)

    def _changed_can_redo(self, can_redo):
        self.emit("can-redo", can_redo)
        self._redo_action.set_sensitive(can_redo)
