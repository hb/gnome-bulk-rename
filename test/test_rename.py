import unittest
import tempfile
import shutil
import os.path
import random

from gi.repository import Gio
from gi.repository import Gtk

import rename
import constants as c

import runtests


def _delete_recursively(gfile):
    if gfile.query_file_type(Gio.FileQueryInfoFlags.NOFOLLOW_SYMLINKS, None) == Gio.FileType.DIRECTORY:
        for fileinfo in gfile.enumerate_children(",".join([Gio.FILE_ATTRIBUTE_STANDARD_NAME, Gio.FILE_ATTRIBUTE_STANDARD_TYPE, Gio.FILE_ATTRIBUTE_STANDARD_IS_HIDDEN]), 0, None):
            _delete_recursively(gfile.get_child(fileinfo.get_name()))
    gfile.delete(None)


def _get_random_dir_name():
    with tempfile.TemporaryDirectory() as tmpdir:
        dirname = os.path.basename(tmpdir)
    return dirname


class _NameMap:
    def __init__(self, row, target_rel_dir=None):
        self.gfile_orig = row[c.FILES_MODEL_COLUMN_GFILE]
        if target_rel_dir is None:
            try:
                base_uri = row[c.FILES_MODEL_COLUMN_GFILE].get_parent().get_uri()
            except AttributeError:
                base_uri = ""
            self.gfile_prev = Gio.file_new_for_commandline_arg(base_uri+"/"+row[c.FILES_MODEL_COLUMN_PREVIEW])
        else:
            self.gfile_prev = target_rel_dir.resolve_relative_path(row[c.FILES_MODEL_COLUMN_PREVIEW])



class TestRenamer(unittest.TestCase):

    def __init__(self, *args):
        unittest.TestCase.__init__(self, *args)
        self.tmp_uri = None
        
        
    def tearDown(self):
        if False:
            print("Left tmp dir intact: {0}".format(self._tmp_dir.get_uri()))
        else:
            _delete_recursively(self._tmp_dir)

    def setUp(self):
        # tmp uri
        if not self.tmp_uri:
            self.tmp_uri = "file://" + tempfile.gettempdir() 
        if not self.tmp_uri.endswith("/"):
            self.tmp_uri = self.tmp_uri + "/"
        
        self._tmp_dir = Gio.file_new_for_commandline_arg(self.tmp_uri + _get_random_dir_name())
        try:
            self._tmp_dir.make_directory(None)
        except:
            self.fail("Base uri does not exist: {0}".format(self.tmp_uri))
        
        
        self._model = Gtk.ListStore(*c.FILES_MODEL_COLUMNS)
        self._mapping = None
        
        self._fail_msg = None
        
        self._two_pass = False
        

    def _add_to_model(self, model, original, preview, filepath):
        row = [None] * len(c.FILES_MODEL_COLUMNS)
        
        row[c.FILES_MODEL_COLUMN_ORIGINAL] = original
        row[c.FILES_MODEL_COLUMN_PREVIEW] = preview
        row[c.FILES_MODEL_COLUMN_GFILE] = filepath
        model.append(row)
        return row


    def _create_and_add_file_to_model(self, model, original, preview, rel_path=None):
        if rel_path is None:
            path = self._tmp_dir
        else:
            path = self._tmp_dir.resolve_relative_path(rel_path)
        filepath = path.resolve_relative_path(original)
        row = self._add_to_model(model, original, preview, filepath)
        
        ss = row[c.FILES_MODEL_COLUMN_GFILE].create(Gio.FileCreateFlags.REPLACE_DESTINATION, None)
        ss.write(row[c.FILES_MODEL_COLUMN_GFILE].get_uri().encode("utf-8"), None)
        ss.close(None)


    def _create_and_add_directory_to_model(self, model, original, preview, rel_path=None):
        if rel_path is None:
            path = self._tmp_dir
        else:
            path = self._tmp_dir.resolve_relative_path(rel_path)
        filepath = path.resolve_relative_path(original)
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
            if not self._two_pass and not mp.gfile_orig.equal(mp.gfile_prev):
                self.assertFalse(mp.gfile_orig.query_exists(None), "File exists, but shouldn't: {0}".format(mp.gfile_orig.get_uri()))
            self.assertTrue(mp.gfile_prev.query_exists(None), "File should exist, but doesn't: {0}".format(mp.gfile_prev.get_uri()))
            
            # check that it's really the right files
            if mp.gfile_prev.query_file_type(Gio.FileQueryInfoFlags.NOFOLLOW_SYMLINKS, None) != Gio.FileType.DIRECTORY:
                try:
                    success, contents = mp.gfile_prev.load_contents(None)[0:2]
                except Exception as ee:
                    self._fail_msg = "Error loading contents of preview file '{0}': {1}".format(mp.gfile_prev.get_uri(), ee.message)
                else:
                    self.assertTrue(success)
                    contents = contents.decode("utf-8").strip()
                    self.assertEqual(contents, mp.gfile_orig.get_uri())


    def _cb_test_rename(self, results):
        self._check_renamed_files()
        Gtk.main_quit()


    def test_rename_easy(self):
        # easy rename of a bunch of files
        for ii in range(10):
            self._create_and_add_file_to_model(self._model, "Test{0}".format(ii), "Renamed{0}".format(ii))
        self._create_and_add_file_to_model(self._model, "Same", "Same")
            
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
    
    
    def test_rename_folders_and_files(self):
        self._create_and_add_directory_to_model(self._model, "dir_1", "renamed_dir_1")
        self._create_and_add_file_to_model(self._model, "file_1", "renamed_file_1")
        self._create_and_add_file_to_model(self._model, "file_2", "renamed_file_2")
        self._create_and_add_directory_to_model(self._model, "dir_2", "renamed_dir_2")

        self._mapping = self._get_mapping(self._model)
        
        rename.Rename(self._model, two_pass=self._two_pass, done_callback=self._cb_test_rename)
        Gtk.main()
        self._cond_fail()


    def test_rename_folders_and_nested_files(self):
        # rename files in a directory structure
        self._create_and_add_directory_to_model(self._model, "dir_1", "renamed_dir_1")
        self._create_and_add_file_to_model(self._model, "file_1", "renamed_file_1")
        self._create_and_add_file_to_model(self._model, "file_2", "renamed_file_2", "dir_1")
        
        # cannot use _get_mapping() with recursive files/dirs
        self._mapping = []
        self._mapping.append(_NameMap(self._model[0]))
        self._mapping.append(_NameMap(self._model[1]))
        self._mapping.append(_NameMap(self._model[2], self._tmp_dir.resolve_relative_path("renamed_dir_1")))
        
        rename.Rename(self._model, two_pass=self._two_pass, done_callback=self._cb_test_rename)
        Gtk.main()
        self._cond_fail()
    
    
    def test_rename_foldertree(self):
        # rename dirs and files in a directory structure
        self._create_and_add_directory_to_model(self._model, "dir_1", "renamed_dir_1")
        self._create_and_add_file_to_model(self._model, "file_1", "renamed_file_1")
        self._create_and_add_directory_to_model(self._model, "dir_2", "renamed_dir_2", "dir_1")
        self._create_and_add_file_to_model(self._model, "file_2", "renamed_file_2", "dir_1")
        self._create_and_add_file_to_model(self._model, "file_3", "renamed_file_3", "dir_1/dir_2")
        
        self._mapping = []
        self._mapping.append(_NameMap(self._model[0]))
        self._mapping.append(_NameMap(self._model[1]))
        self._mapping.append(_NameMap(self._model[2], self._tmp_dir.resolve_relative_path("renamed_dir_1")))
        self._mapping.append(_NameMap(self._model[3], self._tmp_dir.resolve_relative_path("renamed_dir_1")))
        self._mapping.append(_NameMap(self._model[4], self._tmp_dir.resolve_relative_path("renamed_dir_1/renamed_dir_2")))
        
        rename.Rename(self._model, two_pass=self._two_pass, done_callback=self._cb_test_rename)
        Gtk.main()
        self._cond_fail()
    
    
    
    @unittest.expectedFailure
    def test_rename_remote(self):
        raise NotImplementedError
    
