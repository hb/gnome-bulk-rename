import unittest
import tempfile
import shutil
import os.path
import os

from gi.repository import Gio

import check
import constants as c


class TestChecker(unittest.TestCase):

    def assertEmpty(self, ll):
        self.assertEqual(len(ll), 0, "Sequence not empty: '{0}'".format(ll))

    def assertNotEmpty(self, ll):
        self.assertNotEqual(len(ll), 0, "Sequence empty: '{0}'".format(ll))


    def setUp(self):
        nul_row = [""] * len(c.FILES_MODEL_COLUMNS)
        nul_row[c.FILES_MODEL_COLUMN_TOOLTIP] = None

        self._tmp_dir = tempfile.mkdtemp()
        
        def make_sure_gfiles_exist(models):
            for ii, model in enumerate(models):
                folder = os.path.join(self._tmp_dir, str(ii))
                os.mkdir(folder)
                for row in model:
                    filepath = os.path.join(folder, row[c.FILES_MODEL_COLUMN_ORIGINAL])
                    with open(filepath, "w"):
                        pass
                    # model nr 4 tests for existing target
                    if ii == 4:
                        with open(os.path.join(folder, "foo"), "w"):
                            pass
                    row[c.FILES_MODEL_COLUMN_GFILE] = Gio.file_new_for_commandline_arg(filepath)
                    row[c.FILES_MODEL_COLUMN_URI_DIRNAME] = "file://" + folder
        
        # 1: all names stay the same
        self._model_all_same = []
        for ii in range(10):
            row = list(nul_row)
            row[c.FILES_MODEL_COLUMN_ORIGINAL] = "Test{0}".format(ii)
            row[c.FILES_MODEL_COLUMN_PREVIEW] = row[c.FILES_MODEL_COLUMN_ORIGINAL]
            self._model_all_same.append(row)
    
        # 2: some funky names
        self._model_changes = []
        for ii in range(10):
            row = list(nul_row)
            row[c.FILES_MODEL_COLUMN_ORIGINAL] = "Test<>&Me$1^ \u00dfyes$>(_{0}".format(ii)
            row[c.FILES_MODEL_COLUMN_PREVIEW] = "\u00df{0}yes".format(ii+12)
            self._model_changes.append(row)
        
        # 3: circular uris
        self._model_circular = []

        row = list(nul_row)
        row[c.FILES_MODEL_COLUMN_ORIGINAL] = "Test0"
        row[c.FILES_MODEL_COLUMN_PREVIEW] = "Testx"
        self._model_circular.append(row)

        row = list(nul_row)
        row[c.FILES_MODEL_COLUMN_ORIGINAL] = "Test1"
        row[c.FILES_MODEL_COLUMN_PREVIEW] = "Test2"
        self._model_circular.append(row)
        
        row = list(nul_row)
        row[c.FILES_MODEL_COLUMN_ORIGINAL] = "Test2"
        row[c.FILES_MODEL_COLUMN_PREVIEW] = "Test1"
        self._model_circular.append(row)

        row = list(nul_row)
        row[c.FILES_MODEL_COLUMN_ORIGINAL] = "Test3"
        row[c.FILES_MODEL_COLUMN_PREVIEW] = "Testy"
        self._model_circular.append(row)

        # 4: various problems
        self._model_problems = []
        
        row = list(nul_row)
        row[c.FILES_MODEL_COLUMN_ORIGINAL] = "Testa"
        row[c.FILES_MODEL_COLUMN_PREVIEW] = "Testaa"
        self._model_problems.append(row)

        # row 1: target name is empty
        row = list(nul_row)
        row[c.FILES_MODEL_COLUMN_ORIGINAL] = "T1"
        row[c.FILES_MODEL_COLUMN_PREVIEW] = ""
        self._model_problems.append(row)

        # row 2: slash in target
        row = list(nul_row)
        row[c.FILES_MODEL_COLUMN_ORIGINAL] = "T2"
        row[c.FILES_MODEL_COLUMN_PREVIEW] = "T/2"
        self._model_problems.append(row)

        # row 3/4: double targets
        row = list(nul_row)
        row[c.FILES_MODEL_COLUMN_ORIGINAL] = "T3"
        row[c.FILES_MODEL_COLUMN_PREVIEW] = "T3"
        self._model_problems.append(row)
        row = list(nul_row)
        row[c.FILES_MODEL_COLUMN_ORIGINAL] = "T4"
        row[c.FILES_MODEL_COLUMN_PREVIEW] = "T3"
        self._model_problems.append(row)

        row = list(nul_row)
        row[c.FILES_MODEL_COLUMN_ORIGINAL] = "Testz"
        row[c.FILES_MODEL_COLUMN_PREVIEW] = "Testzz"
        self._model_problems.append(row)

        # 5: potential problems
        self._model_potential_problems = []
        
        row = list(nul_row)
        row[c.FILES_MODEL_COLUMN_ORIGINAL] = "Testa"
        row[c.FILES_MODEL_COLUMN_PREVIEW] = "Testaa"
        self._model_potential_problems.append(row)

        row = list(nul_row)
        row[c.FILES_MODEL_COLUMN_ORIGINAL] = "Test1"
        row[c.FILES_MODEL_COLUMN_PREVIEW] = "foo"
        self._model_potential_problems.append(row)

        row = list(nul_row)
        row[c.FILES_MODEL_COLUMN_ORIGINAL] = "Testz"
        row[c.FILES_MODEL_COLUMN_PREVIEW] = "Testzz"
        self._model_potential_problems.append(row)

        # GFile's
        make_sure_gfiles_exist((self._model_all_same, self._model_changes, self._model_circular,
                                self._model_problems, self._model_potential_problems))

    
    def tearDown(self):
        #print(self._tmp_dir)
        shutil.rmtree(self._tmp_dir)
    
    
    def test_all_names_stay_the_same(self):
        chk = check.Checker(self._model_all_same)
        chk.perform_checks()
        self.assertTrue(chk.all_names_stay_the_same)
        self.assertEqual(chk.highest_problem_level, 0)
        self.assertEmpty(chk.circular_uris)


    def test_changes(self):
        chk = check.Checker(self._model_changes)
        chk.perform_checks()
        self.assertFalse(chk.all_names_stay_the_same)
        self.assertEqual(chk.highest_problem_level, 0)
        self.assertEmpty(chk.circular_uris)
    
    def test_circular(self):
        chk = check.Checker(self._model_circular)
        chk.perform_checks()
        self.assertFalse(chk.all_names_stay_the_same)
        self.assertEqual(chk.highest_problem_level, 0)
        self.assertNotEmpty(chk.circular_uris)
        
    def test_problems(self):
        chk = check.Checker(self._model_problems)
        chk.perform_checks()
        self.assertFalse(chk.all_names_stay_the_same)
        self.assertEqual(chk.highest_problem_level, 2)
        self.assertNotEmpty(chk.circular_uris)
        
        self.assertEqual(self._model_problems[1][c.FILES_MODEL_COLUMN_ICON_STOCK], "gtk-dialog-error")
        self.assertIn("Empty target name", self._model_problems[1][c.FILES_MODEL_COLUMN_TOOLTIP])
        
        self.assertEqual(self._model_problems[2][c.FILES_MODEL_COLUMN_ICON_STOCK], "gtk-dialog-error")
        self.assertIn("Slash in target name", self._model_problems[2][c.FILES_MODEL_COLUMN_TOOLTIP])

        self.assertEqual(self._model_problems[3][c.FILES_MODEL_COLUMN_ICON_STOCK], "gtk-dialog-error")
        self.assertIn("Double output filepath", self._model_problems[3][c.FILES_MODEL_COLUMN_TOOLTIP])
        self.assertEqual(self._model_problems[4][c.FILES_MODEL_COLUMN_ICON_STOCK], "gtk-dialog-error")
        self.assertIn("Double output filepath", self._model_problems[4][c.FILES_MODEL_COLUMN_TOOLTIP])
        
        chk.clear_all_warnings_and_errors()
        self.assertEqual(self._model_problems[1][c.FILES_MODEL_COLUMN_ICON_STOCK], "")
        self.assertNotIn("Empty target name", self._model_problems[1][c.FILES_MODEL_COLUMN_TOOLTIP])
        
    
    def test_probable_problem(self):
        chk = check.Checker(self._model_potential_problems)
        chk.perform_checks()
        self.assertFalse(chk.all_names_stay_the_same)
        self.assertEqual(chk.highest_problem_level, 1)
        self.assertEmpty(chk.circular_uris)

        self.assertEqual(self._model_potential_problems[1][c.FILES_MODEL_COLUMN_ICON_STOCK], "gtk-dialog-warning")
        self.assertIn("Target filename already exists on the filesystem", self._model_potential_problems[1][c.FILES_MODEL_COLUMN_TOOLTIP])

        chk.clear_all_warnings_and_errors()
        self.assertEqual(self._model_potential_problems[1][c.FILES_MODEL_COLUMN_ICON_STOCK], "")
        self.assertNotIn("Empty target name", self._model_potential_problems[1][c.FILES_MODEL_COLUMN_TOOLTIP])
