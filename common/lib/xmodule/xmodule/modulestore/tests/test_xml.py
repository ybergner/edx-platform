"""
Tests around our XML modulestore, including importing
well-formed and not-well-formed XML.
"""
import os.path
import unittest
from glob import glob
from mock import patch

from xmodule.course_module import CourseDescriptor
from xmodule.modulestore.xml import XMLModuleStore
from xmodule.modulestore import Location, XML_MODULESTORE_TYPE

from .test_modulestore import check_path_to_location
from xmodule.tests import DATA_DIR


def glob_tildes_at_end(path):
    """
    A wrapper for the `glob.glob` function, but it always returns
    files that end in a tilde (~) at the end of the list of results.
    """
    result = glob(path)
    with_tildes = [f for f in result if f.endswith("~")]
    no_tildes = [f for f in result if not f.endswith("~")]
    return no_tildes + with_tildes


class TestXMLModuleStore(unittest.TestCase):
    """
    Test around the XML modulestore
    """
    def test_path_to_location(self):
        """Make sure that path_to_location works properly"""

        print "Starting import"
        modulestore = XMLModuleStore(DATA_DIR, course_dirs=['toy', 'simple'])
        print "finished import"

        check_path_to_location(modulestore)

    def test_xml_modulestore_type(self):
        store = XMLModuleStore(DATA_DIR, course_dirs=['toy', 'simple'])
        self.assertEqual(store.get_modulestore_type('foo/bar/baz'), XML_MODULESTORE_TYPE)

    def test_unicode_chars_in_xml_content(self):
        # edX/full/6.002_Spring_2012 has non-ASCII chars, and during
        # uniquification of names, would raise a UnicodeError. It no longer does.

        # Ensure that there really is a non-ASCII character in the course.
        with open(os.path.join(DATA_DIR, "toy/sequential/vertical_sequential.xml")) as xmlf:
            xml = xmlf.read()
            with self.assertRaises(UnicodeDecodeError):
                xml.decode('ascii')

        # Load the course, but don't make error modules.  This will succeed,
        # but will record the errors.
        modulestore = XMLModuleStore(DATA_DIR, course_dirs=['toy'], load_error_modules=False)

        # Look up the errors during load. There should be none.
        location = CourseDescriptor.id_to_location("edX/toy/2012_Fall")
        errors = modulestore.get_item_errors(location)
        assert errors == []

    @patch("xmodule.modulestore.xml.glob.glob", side_effect=glob_tildes_at_end)
    def test_tilde_files_ignored(self, _fake_glob):
        modulestore = XMLModuleStore(DATA_DIR, course_dirs=['tilde'], load_error_modules=False)
        course_module = modulestore.modules['edX/tilde/2012_Fall']
        about_location = Location({
            'tag': 'i4x',
            'org': 'edX',
            'course': 'tilde',
            'category': 'about',
            'name': 'index',
        })
        about_module = course_module[about_location]
        self.assertIn("GREEN", about_module.data)
        self.assertNotIn("RED", about_module.data)

    def test_get_courses_for_wiki(self):
        """
        Test the get_courses_for_wiki method
        """
        store = XMLModuleStore(DATA_DIR, course_dirs=['toy', 'simple'])
        for course in store.get_courses():
            course_locations = store.get_courses_for_wiki(course.wiki_slug)
            self.assertEqual(len(course_locations), 1)
            self.assertIn(Location('i4x', 'edX', course.location.course, 'course', '2012_Fall'), course_locations)

        course_locations = store.get_courses_for_wiki('no_such_wiki')
        self.assertEqual(len(course_locations), 0)

        # now set toy course to share the wiki with simple course
        toy_course = store.get_course('edX/toy/2012_Fall')
        toy_course.wiki_slug = 'simple'

        course_locations = store.get_courses_for_wiki('toy')
        self.assertEqual(len(course_locations), 0)

        course_locations = store.get_courses_for_wiki('simple')
        self.assertEqual(len(course_locations), 2)
        for course_number in ['toy', 'simple']:
            self.assertIn(Location('i4x', 'edX', course_number, 'course', '2012_Fall'), course_locations)
