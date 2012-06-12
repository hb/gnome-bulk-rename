import unittest
import tempfile
import shutil
import os.path

from gi.repository import Gio
from gi.repository import Gtk

import rename
import constants as c

class _NameMap:
    def __init__(self, row):
        self.gfile_orig = row[c.FILES_MODEL_COLUMN_GFILE]
        self.orig_uri = self.gfile_orig.get_uri()
        try:
            base_uri = row[c.FILES_MODEL_COLUMN_GFILE].get_parent().get_uri()
        except AttributeError:
            base_uri = ""
        self.gfile_prev = Gio.file_new_for_commandline_arg(base_uri+"/"+row[c.FILES_MODEL_COLUMN_PREVIEW])



class TestRenamer(unittest.TestCase):

    def tearDown(self):
        if False:
            print("Left tmp dir intact: {0}".format(self._tmp_dir))
        else:
            shutil.rmtree(self._tmp_dir)

    def setUp(self):
        self._tmp_dir = tempfile.mkdtemp()
        
        self._model = Gtk.ListStore(*c.FILES_MODEL_COLUMNS)
        self._mapping = None
        
        self._fail_msg = None
        
        self._two_pass = False
        

    def _add_to_model(self, model, original, preview, filepath):
        row = [None] * len(c.FILES_MODEL_COLUMNS)
        
        row[c.FILES_MODEL_COLUMN_ORIGINAL] = original
        row[c.FILES_MODEL_COLUMN_PREVIEW] = preview
        row[c.FILES_MODEL_COLUMN_GFILE] = Gio.file_new_for_commandline_arg(filepath)
        model.append(row)
        return row


    def _create_and_add_file_to_model(self, model, original, preview, rel_path=None):
        if rel_path is None:
            path = self._tmp_dir
        else:
            path = os.path.join(self._tmp_dir, rel_path)
        filepath = os.path.join(path, original)
        row = self._add_to_model(model, original, preview, filepath)
        
        ss = row[c.FILES_MODEL_COLUMN_GFILE].create(Gio.FileCreateFlags.REPLACE_DESTINATION, None)
        ss.write(row[c.FILES_MODEL_COLUMN_GFILE].get_uri().encode("utf-8"), None)
        ss.close(None)


    def _create_and_add_directory_to_model(self, model, original, preview, rel_path=None):
        if rel_path is None:
            path = self._tmp_dir
        else:
            path = os.path.join(self._tmp_dir, rel_path)
        filepath = os.path.join(path, original)
        row = self._add_to_model(model, original, preview, filepath)
        retval = row[c.FILES_MODEL_COLUMN_GFILE].make_directory_with_parents(None)
        self.assertTrue(retval)


    def _get_mapping(self, model):
        mapping = []
        for row in model:
            mapping.append(_NameMap(row))
        return mapping


    def _cond_fail(self):
        if self._fail_msg is not None:
            print(self._fail_msg)
            self.fail(self._fail_msg)


    def _check_renamed_files(self):
        for mp in self._mapping:
            # check that the target files really exist, and source files are gone
            if not self._two_pass:
                self.assertFalse(mp.gfile_orig.query_exists(None), mp.gfile_orig.get_uri())
            self.assertTrue(mp.gfile_prev.query_exists(None), mp.gfile_orig.get_uri())
            
            # check that it's really the right files
            success, contents = mp.gfile_prev.load_contents(None)[0:2]
            self.assertTrue(success)
            contents = contents.decode("utf-8").strip()
            self.assertEqual(contents, mp.gfile_orig.get_uri())


    def _cb_test_rename(self, results):
        try:
            self._check_renamed_files()
        except Exception as ee:
            self._fail_msg = ee.message
        Gtk.main_quit()


    def test_rename_easy(self):
        # easy rename of a bunch of files
        for ii in range(10):
            self._create_and_add_file_to_model(self._model, "Test{0}".format(ii), "Renamed{0}".format(ii))
        self._mapping = self._get_mapping(self._model)
        
        rename.Rename(self._model, two_pass=self._two_pass, done_callback=self._cb_test_rename)
        Gtk.main()
        self._cond_fail()


    def test_rename_cycle(self):
        # rename a bunch of files which cycle
        for ii in range(5):
            self._create_and_add_file_to_model(self._model, "Test{0}".format(ii), "Test{0}".format((ii+1)%5))
        self._mapping = self._get_mapping(self._model)
        self._two_pass = True
        rename.Rename(self._model, two_pass=self._two_pass, done_callback=self._cb_test_rename)
        Gtk.main()
        self._cond_fail()
    
    
    @unittest.expectedFailure
    def test_rename_folders_and_files(self):
        # rename files in a directory structure
        self._create_and_add_directory_to_model(self._model, "dir_1", "renamed_dir_1")
        self._create_and_add_file_to_model(self._model, "file_1", "renamed_file_1")
        self._create_and_add_file_to_model(self._model, "file_2", "renamed_file_2", "dir_1")
        
        self._mapping = self._get_mapping(self._model)
        rename.Rename(self._model, two_pass=self._two_pass, done_callback=self._cb_test_rename)
        Gtk.main()
        self._cond_fail()
    
    
    @unittest.expectedFailure
    def test_rename_foldertree(self):
        raise NotImplementedError
    
    
    @unittest.expectedFailure
    def test_rename_remote(self):
        raise NotImplementedError
    
    