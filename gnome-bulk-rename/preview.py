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
be called during preview (or an endless loop might occur).
The second argument is the files model.

Optionally, a previewer may implement the get_config_widget member function
which is supposed to return a GtkWidget for the previewer configuration.

An optional post_rename() hook will be called after a rename has been done.

After construction, the preview class is supposed to be in a valid state.
Preview classes can show that they are currently in an invalid state by
defining a "valid" member variable and assigning it a False value.
"""

import string
import difflib
import re


import pygtk
pygtk.require('2.0')
import gtk

import gtkutils


def long_substr(model):
    """Brutal force, this could be smarter.

    From a stackoverflow answer."""
    substr = ''
    if len(model) > 1 and len(model[0][0]) > 0:
        for i in range(len(model[0][0])):
            for j in range(len(model[0][0])-i+1):
                if j > len(substr) and all(model[0][0][i:i+j] in x[0] for x in model):
                    substr = model[0][0][i:i+j]
    return substr



class PreviewTranslate(object):
    """General character translation"""

    short_description = "Character translation"
    skip = True

    def __init__(self, refresh_func, model):
        self._translation_table = None

    def set_source_and_target(self, source, target):
        self._translation_table = string.maketrans(source, target)
    
    def preview(self, model):
        if self._translation_table:
            for row in model:
                row[1] = row[0].translate(self._translation_table)


class PreviewReplaceSpacesWithUnderscores(PreviewTranslate):

    short_description =  "Replace spaces with underscores"
    skip = True
    priority = 0.4
    
    def __init__(self, refresh_func, model):
        PreviewTranslate.__init__(self, refresh_func, model)
        self.set_source_and_target(" ", "_")

    def get_config_widget(self):
        hbox = gtk.HBox(False, 0)
        hbox.pack_start(gtk.Label("This mode doesn't have configuration options."), False)
        return hbox

class PreviewReplaceAllNonAlphanumericWithUnderscores(object):
    
    short_description = "Replace all non-alphanumeric characters with underscores"
    skip = True

    def __init__(self, refresh_func, model):
        self._pattern = re.compile("[^a-zA-Z0-9_.]")

    def preview(self, model):
        for row in model:
            row[1] = self._pattern.sub("_", unicode(row[0]))
    

class PreviewReplaceLongestSubstring(object):

    short_description = "Modify common name part"
    skip = True

    def __init__(self, refresh_func, model):
        self._refresh_func = refresh_func

        self._longest_common_substring = None
        self._valid = True

        # config widget
        self._config_widget = gtk.HBox(False, 8)
        self._longest_common_substring_label = gtk.Label()
        self._config_widget.pack_start(self._longest_common_substring_label, False)
        self._replacement_string_entry = gtk.Entry()
        self._config_widget.pack_start(self._replacement_string_entry)

        self._on_model_changed(model)

        self._replacement_string_entry.connect("changed", self._on_replacement_string_entry_changed)


    def preview(self, model):
        for row in model:
            row[1] = row[0].replace(self._longest_common_substring, self._replacement_string_entry.get_text())

    def get_config_widget(self):
        return self._config_widget

    def post_rename(self, model):
        self._on_model_changed(model)
        
    def grab_focus(self):
        self._replacement_string_entry.grab_focus()

    @property
    def valid(self):
        return self._valid

    def _on_replacement_string_entry_changed(self, editable):
        # TODO: sanity check (search for /)
        self._refresh_func()


    def _on_model_changed(self, model, path=None, iter=None):
        self._longest_common_substring = long_substr(model)
        if len(self._longest_common_substring) < 2:
            self._valid = False
            msg = "File names don't have a common substring." 
        else:
            self._valid = True
            msg = "".join(["Replace the part <b>", self._longest_common_substring, "</b> with"])
        
        self._longest_common_substring_label.set_markup(msg)

        if not self.valid:
            self._replacement_string_entry.set_sensitive(False)
        else:
            self._replacement_string_entry.set_text(self._longest_common_substring)
            self._replacement_string_entry.set_sensitive(True)


class PreviewSearchReplace(object):
    """Search/replace previewer"""
    
    short_description = "Search / replace"
    priority = 0.1
    
    def __init__(self, refresh_func, model):
        self._refresh_func = refresh_func
        
        self._valid = True
        
        self._config_widget = gtk.Table(2, 3)
        self._config_widget.set_col_spacing(0, 12)
        self._config_widget.set_col_spacing(1, 12)
        self._config_widget.set_row_spacings(4)

        self._config_widget.attach(gtk.Label("Search for:"), 0, 1, 0, 1, xoptions=gtk.SHRINK)
        self._search_entry = gtk.Entry()
        self._search_entry.connect("changed", self._on_config_changed_cb)
        self._config_widget.attach(self._search_entry, 1, 2, 0, 1)
        self._search_string = ""
        
        self._config_widget.attach(gtk.Label("Replace with:"), 0, 1, 1, 2, xoptions=gtk.SHRINK)
        self._replace_entry = gtk.Entry()
        self._replace_entry.connect("changed", self._on_config_changed_cb)
        self._config_widget.attach(self._replace_entry, 1, 2, 1, 2)
        
        self._case_insensitive_check = gtk.CheckButton("Case insensitive")
        self._case_insensitive_check.connect("toggled", self._on_config_changed_cb)
        self._config_widget.attach(self._case_insensitive_check, 2, 3, 0, 1)

        self._regular_expression_check = gtk.CheckButton("Regular expressions")
        self._regular_expression_check.connect("toggled", self._on_config_changed_cb)
        self._config_widget.attach(self._regular_expression_check, 2, 3, 1, 2)
        
        
    def preview(self, model):
        if self._search_string != "":
            replace_string = self._replace_entry.get_text()
            for row in model:
                if self._case_insensitive_check.get_active():
                    source_string = row[0].lower()
                else:
                    source_string = row[0]

                if self._regular_expression_check.get_active():
                    row[1] = re.sub(self._search_string, replace_string, source_string)
                else:                 
                    row[1] = source_string.replace(self._search_string, replace_string)
        else:
            for row in model:
                row[1] = row[0]

    def get_config_widget(self):
        return self._config_widget
    
    
    def grab_focus(self):
        self._search_entry.grab_focus()
    
    @property
    def valid(self):
        return self._valid
    
    
    def _on_config_changed_cb(self, dummy):
        self._check_validity_of_search_string()
        self._refresh_func()

    
    def _check_validity_of_search_string(self):
        # get search string
        if self._case_insensitive_check.get_active():
            self._search_string = entry.get_text().lower()
        else:
            self._search_string = self._search_entry.get_text()
            
        self._valid = True
        if self._regular_expression_check.get_active():
            try:
                re.compile(self._search_string)
            except re.error:
                self._valid = False


class PreviewToUpper(object):
    
    short_description = "Convert to upper case"
    skip = True
    
    def __init__(self, refresh_func, model):
        pass
    
    def preview(self, model):
        for row in model:
            row[1] = row[0].upper()


class PreviewToLower(object):
    
    short_description = "Convert to lower case"
    skip = True
    
    def __init__(self, refresh_func, model):
        pass
    
    def preview(self, model):
        for row in model:
            row[1] = row[0].lower()


class PreviewToTitle(object):
    
    short_description = "Convert to title case"
    skip = True
    
    def __init__(self, refresh_func, model):
        pass
    
    def preview(self, model):
        for row in model:
            row[1] = row[0].title()


class PreviewEnumerate(object):
    
    short_description = "Enumerations"
    
    def __init__(self, refresh_func, model):
        self._refresh_func = refresh_func
        
        # config widget
        table = gtk.Table(4, 2)
        table.set_col_spacings(12)
        table.set_row_spacings(4)

        row = -1
        
        # starting value
        row += 1
        table.attach(gtk.Label("Starting value:"), 0, 1, row, row+1, xoptions=gtk.FILL)
        adjustment = gtk.Adjustment(1, 1, 999999, 1, 10)
        align = gtk.Alignment()
        spinner = gtk.SpinButton(adjustment, 1, 0)
        spinner.set_update_policy(gtk.UPDATE_IF_VALID)
        spinner.connect("value-changed", self._trigger_refresh)
        align.add(spinner)
        table.attach(align, 1, 2, row, row+1, xoptions=gtk.FILL)
        self._start_value_spinner = spinner

        # increment
        row += 1
        table.attach(gtk.Label("Increment:"), 0, 1, row, row+1, xoptions=gtk.FILL)
        adjustment = gtk.Adjustment(1, 1, 1000, 1, 10)
        align = gtk.Alignment()
        spinner = gtk.SpinButton(adjustment, 1, 0)
        spinner.set_update_policy(gtk.UPDATE_IF_VALID)
        spinner.connect("value-changed", self._trigger_refresh)
        align.add(spinner)
        table.attach(align, 1, 2, row, row+1, xoptions=gtk.FILL)
        self._increment_spinner = spinner

        # zero padding
        row += 1
        table.attach(gtk.Label("Zero padding:"), 0, 1, row, row+1, xoptions=gtk.FILL)
        adjustment = gtk.Adjustment(1, 1, 10, 1, 1)
        align = gtk.Alignment()
        spinner = gtk.SpinButton(adjustment, 1, 0)
        spinner.set_update_policy(gtk.UPDATE_IF_VALID)
        spinner.connect("value-changed", self._trigger_refresh)
        align.add(spinner)
        table.attach(align, 1, 2, row, row+1, xoptions=gtk.FILL)
        self._zero_padding_spinner = spinner

        # text
        row += 1
        table.attach(gtk.Label("Text:"), 0, 1, row, row+1, xoptions=gtk.FILL)
        entry = gtk.Entry()
        entry.connect("changed", self._trigger_refresh)
        entry.set_text(".")
        table.attach(entry, 1, 2, row, row+1, xoptions=gtk.FILL)
        self._text_entry = entry

        # format
        row += 1
        table.attach(gtk.Label("Format:"), 0, 1, row, row+1, xoptions=gtk.FILL)
        combobox = gtk.combo_box_new_text()
        combobox.append_text("Number - Text - Old Name")
        combobox.append_text("Old Name - Text - Number")
        combobox.append_text("Text - Number")
        combobox.append_text("Number - Text")
        combobox.connect("changed", self._trigger_refresh)
        combobox.set_active(0)
        align = gtk.Alignment()
        align.add(combobox)
        table.attach(align, 1, 2, row, row+1, xoptions=gtk.FILL)
        self._format_combobox = combobox
        
        self._config_widget = table


    def preview(self, model):
        value = self._start_value_spinner.get_value_as_int()
        increment = self._increment_spinner.get_value_as_int()
        zero_padding = self._zero_padding_spinner.get_value_as_int()
        format = self._format_combobox.get_active_text()
        text = self._text_entry.get_text()

        if format == "Number - Text - Old Name":
            ff = "%%0%dd%%s%%s" % zero_padding  
            for row in model:
                row[1] = ff % (value, text, row[0])
                value += increment
        elif format == "Old Name - Text - Number":
            ff = "%%s%%s%%0%dd" % zero_padding
            for row in model:
                row[1] = ff % (row[0], text, value)
                value += increment
        elif format == "Text - Number":
            ff = "%%s%%0%dd" % zero_padding
            for row in model:
                row[1] = ff % (text, value)
                value += increment
        elif format == "Number - Text":
            ff = "%%0%dd%%s" % zero_padding
            for row in model:
                row[1] = ff % (value, text)
                value += increment
        else:
            row[1] = row[0]
        
    
    
    def get_config_widget(self):
        return self._config_widget


    def _trigger_refresh(self, dummy):
        self._refresh_func()


class PreviewCommonModificationsSimple(object):
    """This previewer is intended as a fallback for the longest substring replacement
    in cases where no such substring exists"""
    
    short_description = "Simple common modifications"
    skip = True
    
    PREVIEWS_SELECTION_COLUMNS = (str, object)

    def __init__(self, refresh_func, model):
        self._refresh_func = refresh_func
        self._model = model

        self._current_previewer = None

        previewers = [PreviewReplaceSpacesWithUnderscores,PreviewReplaceAllNonAlphanumericWithUnderscores,PreviewToUpper,PreviewToLower,PreviewToTitle]

        # config widget
        previews_model = gtk.ListStore(*PreviewCommonModificationsSimple.PREVIEWS_SELECTION_COLUMNS)
        previews_combobox = gtk.ComboBox(previews_model)
        cell = gtk.CellRendererText()
        previews_combobox.pack_start(cell)
        previews_combobox.add_attribute(cell, "text", 0)
        previews_combobox.connect("changed", self._on_previews_combobox_changed)
        self._config_widget = previews_combobox

        for previewer in previewers:
            previews_model.append((previewer.short_description, previewer))

        previews_combobox.set_active(0)


    def preview(self, model):
        try:
            self._current_previewer.preview(model)
        except AttributeError:
            pass


    def get_config_widget(self):
        return self._config_widget

    def post_rename(self, model):
        try:
            self._current_previewer.post_rename(model)
        except AttributeError:
            pass


    def _on_previews_combobox_changed(self, combobox):
        row = combobox.get_model()[combobox.get_active()]
        self._current_previewer = row[1](self._refresh_func, self._model)
        self._refresh_func()


class PreviewCommonModifications(object):
    
    short_description = "Common specialized modifications"

    PREVIEWS_SELECTION_COLUMNS = (str, object)
    PREVIEWS_SELECTION_COLUMN_SHORT_DESCRIPTION = 0
    PREVIEWS_SELECTION_COLUMN_PREVIEW = 1

    def __init__(self, refresh_func, model):
        self._refresh_func = refresh_func
        self._model = model

        self._current_previewer = None

        # which previewers should be in the common block?
        previewers = [PreviewReplaceLongestSubstring, PreviewReplaceSpacesWithUnderscores, PreviewReplaceAllNonAlphanumericWithUnderscores,PreviewToUpper,PreviewToLower,PreviewToTitle]

        # config widget
        self._config_widget = gtk.VBox(False, 4)

        # subconfig widget
        self._subconfig_widget = gtk.VBox(False, 0)

        # combo box for selection
        previews_model = gtk.ListStore(*PreviewCommonModifications.PREVIEWS_SELECTION_COLUMNS)
        previews_combobox = gtk.ComboBox(previews_model)
        cell = gtk.CellRendererText()
        previews_combobox.pack_start(cell)
        previews_combobox.add_attribute(cell, "text", 0)
        previews_combobox.connect("changed", self._on_previews_combobox_changed)
        self._config_widget.pack_start(previews_combobox, False)

        for previewer in previewers:
            previews_model.append((previewer.short_description, previewer))

        previews_combobox.set_active(0)

        self._config_widget.pack_start(self._subconfig_widget)

        self._config_widget.show_all()


    def preview(self, model):
        try:
            self._current_previewer.preview(model)
        except AttributeError:
            pass


    def get_config_widget(self):
        return self._config_widget

    def post_rename(self, model):
        try:
            self._current_previewer.post_rename(model)
        except AttributeError:
            pass

    @property
    def valid(self):
        try:
            valid = self._current_previewer.valid
        except AttributeError:
            valid = True
        return valid

    def _on_previews_combobox_changed(self, combobox):
        row = combobox.get_model()[combobox.get_active()]
        gtkutils.clear_gtk_container(self._subconfig_widget)
        self._current_previewer = row[1](self._refresh_func, self._model)
        try:
            self._subconfig_widget.pack_start(self._current_previewer.get_config_widget())
        except AttributeError:
            pass
        
        self._subconfig_widget.show_all()
            
        self._refresh_func()


class PreviewNoop(object):
    """Source name is identical to target name."""

    short_description = "No change"
    skip = True
    priority = 0.11

    def __init__(self, refresh_func, model):
        pass
        
    def preview(self, model):
        for row in model:
            row[1] = row[0]


class PreviewReplaceEverySecondWithFixedString(object):
    """Just for testing"""
    
    short_description = "Replace with fixed string"
    skip = True
    priority = 0.8
    
    def __init__(self, refresh_func, model):
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
    skip = True
    priority = 0.81
    
    def __init__(self, refresh_func, model):
        pass

    def preview(self, model):
        if not model:
            return
        for ii in range(1, len(model)):
            model[ii-1][1] = model[ii][0]
        model[len(model)-1][1] = model[0][0]



class PreviewToggleSpaceUnderscore(PreviewTranslate):
    
    short_description = "Toggle space underscore"
    skip = True
    ct = 0
    
    def __init__(self, refresh_func, model):
        pass
    
    def preview(self, model):
        if (PreviewToggleSpaceUnderscore.ct % 2) == 0:
            self.set_source_and_target(" ", "_")
        else:
            self.set_source_and_target("_", " ")
        PreviewTranslate.preview(self, model)
        PreviewToggleSpaceUnderscore.ct += 1
