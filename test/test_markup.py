import unittest

from gi.repository import GLib

import markup
import constants as c

class TestMarkup(unittest.TestCase):

    def setUp(self):
        
        nul_row = [""] * len(c.FILES_MODEL_COLUMNS)
        self._model = []

        def append_row(original, preview=None):
            row = list(nul_row)
            row[c.FILES_MODEL_COLUMN_ORIGINAL] = original
            row[c.FILES_MODEL_COLUMN_PREVIEW] = row[c.FILES_MODEL_COLUMN_ORIGINAL] if preview is None else preview
            self._model.append(row)


        # 0: row with a easy name, source identical to preview
        append_row("testName")

        # 1: row with special characters, source identical to preview
        append_row("\u00d6ffentliche Stra\u00dfe")

        # 2: row with special characters that form markup, source identical to preview
        append_row("Test<>&Me$1^")

        # 3: row with easy name, preview is source with prefix
        append_row("easy", "my_easy")

        # 4: row with easy name, preview is source with suffix
        append_row("easy", "easy_rider")

        # 5: row with easy name, preview is source with additional characters in the middle
        append_row("easy", "eafoosy")

        # 6: row with easy name, preview is source with changed characters
        append_row("eeeeasyyyy", "eeeettyyyy")

        # 7: row with complicated name, preview is source with prefix
        append_row("Test<>&Me$1^ \u00dfyes$>(", "pxTest<>&Me$1^ \u00dfyes$>(")

        # 8: row with complicated name, preview is source with suffix
        append_row("Test<>&Me$1^ \u00dfyes$>(", "Test<>&Me$1^ \u00dfyes$>(sx")
        
        # 9: row with complicated name, preview is source with additional characters in the middle
        append_row("Test<>&Me$1^\u00dfyes$>(", "Test<>&Me$1^ huh  \u00dfyes$>(")

        # 10: row with complicated name, preview is source with end stuff omitted
        append_row("Test<>&Me$1^ \u00dfyes$>(", "Test<>&Me$1^ \u00dfye")

        # 11: row with complicated name, preview is source with beginning stuff omitted
        append_row("Test<>&Me$1^ \u00dfyes$>(", "t<>&Me$1^ \u00dfyes$>(")

        # 12: row with complicated name, preview is source with middle stuff omitted
        append_row("Test<>&Me$1^ \u00dfyes$>(", "Test<>&Me \u00dfyes$>(")


    def _assertIdentical(self, row_num):
        # markuped rows are identical to their respective original parts
        self.assertEqual(self._model[row_num][c.FILES_MODEL_COLUMN_ORIGINAL],
                         self._model[row_num][c.FILES_MODEL_COLUMN_MARKUP_ORIGINAL])
        self.assertEqual(self._model[row_num][c.FILES_MODEL_COLUMN_PREVIEW],
                         self._model[row_num][c.FILES_MODEL_COLUMN_MARKUP_PREVIEW])

    def _assertIdenticalExceptEscape(self, row_num):
        self.assertEqual(GLib.markup_escape_text(self._model[row_num][c.FILES_MODEL_COLUMN_ORIGINAL]),
                         self._model[row_num][c.FILES_MODEL_COLUMN_MARKUP_ORIGINAL])
        self.assertEqual(GLib.markup_escape_text(self._model[row_num][c.FILES_MODEL_COLUMN_PREVIEW]),
                         self._model[row_num][c.FILES_MODEL_COLUMN_MARKUP_PREVIEW])


    def _assertAllRowsConsidered(self, *tuples):
        all_rows = set(range(len(self._model)))
        remainder = all_rows.difference(*[set(el) for el in tuples])
        self.assertEqual(len(remainder), 0,
                         "Test missing the following rows: {0}".format(sorted(list(remainder))))


    def test_MarkupNoop(self):
        markup.MarkupNoop().markup(self._model)

        identical = (0, 1, 3, 4, 5, 6)
        markup_escaped = (2, 7, 8, 9, 10, 11, 12)
        
        self._assertAllRowsConsidered(identical, markup_escaped) 
        
        for el in identical:
            self._assertIdentical(el)

        for el in markup_escaped:
            self._assertIdenticalExceptEscape(el)


    def test_MarkupColor(self):
        delete_color = "Palegreen1"
        insert_color="LightSkyBlue1"
        replace_color="LightSalmon1"
        
        markup.MarkupColor(delete_color=delete_color, insert_color=insert_color, replace_color=replace_color).markup(self._model)
        
        def tags(color, ss, idx1, idx2):
            return GLib.markup_escape_text(ss[0:idx1]) + "<span bgcolor='{0}'>".format(color) + GLib.markup_escape_text(ss[idx1:idx2]) + "</span>" + GLib.markup_escape_text(ss[idx2:])
        
        def delete_tags(ss, idx1, idx2):
            return tags(delete_color, ss, idx1, idx2)
        
        def insert_tags(ss, idx1, idx2):
            return tags(insert_color, ss, idx1, idx2)
        
        def replace_tags(ss, idx1, idx2):
            return tags(replace_color, ss, idx1, idx2)
        
        identical = (0, 1)
        markup_escaped = (2, )
        
        # row, idx1, idx2
        original_replace = (
                            (6, 4, 6),
                            )
        original_delete = (
                           (10, 16, 20),
                           (11, 0, 3),
                           (12, 9, 12)
                           )

        preview_insert = (
                          (3, 0, 3),
                          (4, 4, 10),
                          (5, 2, 5),
                          (7, 0, 2),
                          (8, 20, 22),
                          (9, 12, 18),
                          )
        preview_replace = (
                           (6, 4, 6),
                           )

        self._assertAllRowsConsidered(identical, markup_escaped,
                                      [el[0] for el in original_replace],
                                      [el[0] for el in original_delete],
                                      [el[0] for el in preview_insert],
                                      [el[0] for el in preview_replace],
                                      )
        
        for el in identical:
            self._assertIdentical(el)
        
        for el in markup_escaped:
            self._assertIdenticalExceptEscape(el)

        for row_num, idx1, idx2 in original_replace:
            row = self._model[row_num]
            self.assertEqual(row[c.FILES_MODEL_COLUMN_MARKUP_ORIGINAL],
                             replace_tags(row[c.FILES_MODEL_COLUMN_ORIGINAL], idx1, idx2))

        for row_num, idx1, idx2 in original_delete:
            row = self._model[row_num]
            self.assertEqual(row[c.FILES_MODEL_COLUMN_MARKUP_ORIGINAL],
                             delete_tags(row[c.FILES_MODEL_COLUMN_ORIGINAL], idx1, idx2))
        
        for row_num, idx1, idx2 in preview_insert:
            row = self._model[row_num]
            self.assertEqual(row[c.FILES_MODEL_COLUMN_MARKUP_PREVIEW],
                             insert_tags(row[c.FILES_MODEL_COLUMN_PREVIEW], idx1, idx2))
        
        for row_num, idx1, idx2 in preview_replace:
            row = self._model[row_num]
            self.assertEqual(row[c.FILES_MODEL_COLUMN_MARKUP_ORIGINAL],
                             replace_tags(row[c.FILES_MODEL_COLUMN_ORIGINAL], idx1, idx2))
