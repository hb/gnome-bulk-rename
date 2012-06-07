import unittest
import tempfile
import shutil
import os.path

from gi.repository import Gio

import check
import constants as c


class TestChecker(unittest.TestCase):

    def assertEmpty(self, ll):
        self.assertEqual(len(ll), 0)


    def setUp(self):
        nul_row = [""] * len(c.FILES_MODEL_COLUMNS)

        self._tmp_dir = tempfile.mkdtemp()
        
        # 1: all names stay the same
        self._model_all_same = []
        for ii in range(10):
            row = list(nul_row)
            
            row[c.FILES_MODEL_COLUMN_ORIGINAL] = "Test{0}".format(ii)
            row[c.FILES_MODEL_COLUMN_PREVIEW] = row[c.FILES_MODEL_COLUMN_ORIGINAL]
            filepath = os.path.join(self._tmp_dir, row[c.FILES_MODEL_COLUMN_ORIGINAL])
            with open(filepath, "w"):
                pass
            row[c.FILES_MODEL_COLUMN_GFILE] = Gio.file_new_for_commandline_arg(filepath)
            
            self._model_all_same.append(row)
    
    
    def tearDown(self):
        shutil.rmtree(self._tmp_dir)
    
    
    def test_all_names_stay_the_same(self):
        chk = check.Checker(self._model_all_same)
        chk.perform_checks()
        self.assertTrue(chk.all_names_stay_the_same)
        self.assertEqual(chk.highest_problem_level, 0)
        self.assertEmpty(chk.circular_uris)

