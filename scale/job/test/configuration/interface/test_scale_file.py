#@PydevCodeAnalysisIgnore

import django
from django.test import TestCase
from mock import patch

from job.configuration.interface.scale_file import ScaleFileDescription


class TestScaleFileDescriptionMediaTypeAllowed(TestCase):

    def setUp(self):
        django.setup()

    def test_accept_all(self):
        '''Tests calling ScaleFileDescription.is_media_type_allowed() when accepting all media types.'''

        self.assertTrue(ScaleFileDescription().is_media_type_allowed(u'application/json'))
        self.assertTrue(ScaleFileDescription().is_media_type_allowed(u'application/x-some-crazy-thing'))

    def test_accept_specific(self):
        '''Tests calling ScaleFileDescription.is_media_type_allowed() when accepting specific media types.'''

        file_desc = ScaleFileDescription()
        file_desc.add_allowed_media_type(None)  # Don't blow up
        file_desc.add_allowed_media_type(u'application/json')
        file_desc.add_allowed_media_type(u'text/plain')

        self.assertTrue(file_desc.is_media_type_allowed(u'application/json'))
        self.assertTrue(file_desc.is_media_type_allowed(u'text/plain'))
        self.assertFalse(file_desc.is_media_type_allowed(u'application/x-some-crazy-thing'))
