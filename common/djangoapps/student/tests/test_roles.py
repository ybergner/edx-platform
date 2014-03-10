"""
Tests of student.roles
"""

from django.test import TestCase

from courseware.tests.factories import UserFactory, StaffFactory, InstructorFactory
from student.tests.factories import AnonymousUserFactory

from student.roles import GlobalStaff, CourseRole, CourseStaffRole
from xmodule.modulestore.django import loc_mapper
from xmodule.modulestore.locations import Location, SlashSeparatedCourseKey


class RolesTestCase(TestCase):
    """
    Tests of student.roles
    """

    def setUp(self):
        self.course_id = SlashSeparatedCourseKey('edX', 'toy', '2012_Fall')
        self.course_loc = self.course_id.make_usage_key('course', '2012_Fall')
        self.anonymous_user = AnonymousUserFactory()
        self.student = UserFactory()
        self.global_staff = UserFactory(is_staff=True)
        self.course_staff = StaffFactory(course=self.course_id)
        self.course_instructor = InstructorFactory(course=self.course_id)

    def test_global_staff(self):
        self.assertFalse(GlobalStaff().has_user(self.student))
        self.assertFalse(GlobalStaff().has_user(self.course_staff))
        self.assertFalse(GlobalStaff().has_user(self.course_instructor))
        self.assertTrue(GlobalStaff().has_user(self.global_staff))

    def test_group_name_case_insensitive(self):
        uppercase_course_id = "ORG/COURSE/NAME"
        lowercase_course_id = uppercase_course_id.lower()
        uppercase_course_key = SlashSeparatedCourseKey.from_deprecated_string(uppercase_course_id)
        lowercase_course_key = SlashSeparatedCourseKey.from_deprecated_string(lowercase_course_id)

        lowercase_group = "role_org/course/name"
        uppercase_group = lowercase_group.upper()

        lowercase_user = UserFactory(groups=lowercase_group)
        uppercase_user = UserFactory(groups=uppercase_group)

        self.assertTrue(CourseRole("role", lowercase_course_key).has_user(lowercase_user))
        self.assertTrue(CourseRole("role", uppercase_course_key).has_user(lowercase_user))
        self.assertTrue(CourseRole("role", lowercase_course_key).has_user(uppercase_user))
        self.assertTrue(CourseRole("role", uppercase_course_key).has_user(uppercase_user))

    def test_course_role(self):
        """
        Test that giving a user a course role enables access appropriately
        """
        course_locator = loc_mapper().translate_location(self.course_loc, add_entry_if_missing=True)
        self.assertFalse(
            CourseStaffRole(self.course_id).has_user(self.student),
            "Student has premature access to {}".format(unicode(course_locator))
        )
        self.assertFalse(
            CourseStaffRole(self.course_id).has_user(self.student),
            "Student has premature access to {}".format(self.course_id)
        )
        CourseStaffRole(self.course_id).add_users(self.student)
        self.assertTrue(
            CourseStaffRole(self.course_id).has_user(self.student),
            "Student doesn't have access to {}".format(unicode(course_locator))
        )
        self.assertTrue(
            CourseStaffRole(self.course_id).has_user(self.student),
            "Student doesn't have access to {}".format(unicode(self.course_id))
        )
        # now try accessing something internal to the course
        vertical_locator = course_locator.course_key.make_usage_key('vertical', 'madeup')
        vertical_location = self.course_id.make_usage_key(block_type='vertical', name='madeuptoo')
        self.assertTrue(
            CourseStaffRole(self.course_id).has_user(self.student),
            "Student doesn't have access to {}".format(unicode(vertical_locator))
        )
        self.assertTrue(
            CourseStaffRole(self.course_id).has_user(self.student),
            "Student doesn't have access to {}".format(unicode(vertical_location.url()))
        )
