from __future__ import unicode_literals

import datetime
import json
import time

import django
from django.test import TestCase, TransactionTestCase
from django.utils.timezone import utc, now
from mock import patch
from rest_framework import status

import batch.test.utils as batch_test_utils
import error.test.utils as error_test_utils
import job.test.utils as job_test_utils
import storage.test.utils as storage_test_utils
import trigger.test.utils as trigger_test_utils
import util.rest as rest_util
from error.models import Error
from job.models import JobType
from vault.secrets_handler import SecretsHandler


class TestJobsView(TestCase):

    def setUp(self):
        django.setup()

        self.job_type1 = job_test_utils.create_job_type(name='scale-batch-creator', version='1.0', category='test-1')
        self.job1 = job_test_utils.create_job(job_type=self.job_type1, status='RUNNING')

        self.job_type2 = job_test_utils.create_job_type(name='test2', version='1.0', category='test-2')
        self.job2 = job_test_utils.create_job(job_type=self.job_type2, status='PENDING')

        self.job3 = job_test_utils.create_job(is_superseded=True)

    def test_successful(self):
        """Tests successfully calling the jobs view."""

        url = rest_util.get_url('/jobs/')
        response = self.client.generic('GET', url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)

        result = json.loads(response.content)
        self.assertEqual(len(result['results']), 2)
        for entry in result['results']:
            expected = None
            if entry['id'] == self.job1.id:
                expected = self.job1
            elif entry['id'] == self.job2.id:
                expected = self.job2
            else:
                self.fail('Found unexpected result: %s' % entry['id'])
            self.assertEqual(entry['job_type']['name'], expected.job_type.name)
            self.assertEqual(entry['job_type_rev']['job_type']['id'], expected.job_type.id)

    def test_status(self):
        """Tests successfully calling the jobs view filtered by status."""

        url = rest_util.get_url('/jobs/?status=RUNNING')
        response = self.client.generic('GET', url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)

        result = json.loads(response.content)
        self.assertEqual(len(result['results']), 1)
        self.assertEqual(result['results'][0]['job_type']['id'], self.job1.job_type.id)

    def test_job_id(self):
        """Tests successfully calling the jobs view filtered by job identifier."""

        url = rest_util.get_url('/jobs/?job_id=%s' % self.job1.id)
        response = self.client.generic('GET', url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)

        result = json.loads(response.content)
        self.assertEqual(len(result['results']), 1)
        self.assertEqual(result['results'][0]['id'], self.job1.id)

    def test_job_type_id(self):
        """Tests successfully calling the jobs view filtered by job type identifier."""

        url = rest_util.get_url('/jobs/?job_type_id=%s' % self.job1.job_type.id)
        response = self.client.generic('GET', url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)

        result = json.loads(response.content)
        self.assertEqual(len(result['results']), 1)
        self.assertEqual(result['results'][0]['job_type']['id'], self.job1.job_type.id)

    def test_job_type_name(self):
        """Tests successfully calling the jobs view filtered by job type name."""

        url = rest_util.get_url('/jobs/?job_type_name=%s' % self.job1.job_type.name)
        response = self.client.generic('GET', url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)

        result = json.loads(response.content)
        self.assertEqual(len(result['results']), 1)
        self.assertEqual(result['results'][0]['job_type']['name'], self.job1.job_type.name)

    def test_job_type_category(self):
        """Tests successfully calling the jobs view filtered by job type category."""

        url = rest_util.get_url('/jobs/?job_type_category=%s' % self.job1.job_type.category)
        response = self.client.generic('GET', url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)

        result = json.loads(response.content)
        self.assertEqual(len(result['results']), 1)
        self.assertEqual(result['results'][0]['job_type']['category'], self.job1.job_type.category)

    def test_error_category(self):
        """Tests successfully calling the jobs view filtered by error category."""

        error = error_test_utils.create_error(category='DATA')
        job = job_test_utils.create_job(error=error)

        url = rest_util.get_url('/jobs/?error_category=%s' % error.category)
        response = self.client.generic('GET', url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)

        result = json.loads(response.content)
        self.assertEqual(len(result['results']), 1)
        self.assertEqual(result['results'][0]['id'], job.id)
        self.assertEqual(result['results'][0]['error']['category'], error.category)

    def test_superseded(self):
        """Tests getting superseded jobs."""

        url = rest_util.get_url('/jobs/?include_superseded=true')
        response = self.client.generic('GET', url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)

        result = json.loads(response.content)
        self.assertEqual(len(result['results']), 3)

    def test_batch(self):
        """Tests filtering jobs by batch"""
        batch_job = batch_test_utils.create_batch_job(job=self.job1)

        url = rest_util.get_url('/jobs/?batch_id=%d' % batch_job.batch.id)
        response = self.client.generic('GET', url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)

        result = json.loads(response.content)
        self.assertEqual(len(result['results']), 1)
        self.assertEqual(result['results'][0]['id'], self.job1.id)

    def test_order_by(self):
        """Tests successfully calling the jobs view with sorting."""

        job_type1b = job_test_utils.create_job_type(name='scale-batch-creator', version='2.0', category='test-1')
        job_test_utils.create_job(job_type=job_type1b, status='RUNNING')

        job_type1c = job_test_utils.create_job_type(name='scale-batch-creator', version='3.0', category='test-1')
        job_test_utils.create_job(job_type=job_type1c, status='RUNNING')

        url = rest_util.get_url('/jobs/?order=job_type__name&order=-job_type__version')
        response = self.client.generic('GET', url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)

        result = json.loads(response.content)
        self.assertEqual(len(result['results']), 4)
        self.assertEqual(result['results'][0]['job_type']['id'], job_type1c.id)
        self.assertEqual(result['results'][1]['job_type']['id'], job_type1b.id)
        self.assertEqual(result['results'][2]['job_type']['id'], self.job_type1.id)
        self.assertEqual(result['results'][3]['job_type']['id'], self.job_type2.id)


class TestJobDetailsView(TestCase):

    def setUp(self):
        django.setup()

        self.country = storage_test_utils.create_country()
        self.file = storage_test_utils.create_file(countries=[self.country])

        job_interface = {
            'version': '1.0',
            'command': 'test_cmd',
            'command_arguments': 'test_arg',
            'input_data': [{
                'type': 'property',
                'name': 'input_field',
            }, {
                'type': 'file',
                'name': 'input_file',
            }, {
                'type': 'files',
                'name': 'input_files',
            }],
            'output_data': [{
                'type': 'file',
                'name': 'output_file',
            }, {
                'type': 'files',
                'name': 'output_files',
            }],
            'shared_resources': [],
        }

        job_data = {
            'input_data': []
        }
        job_results = {
            'output_data': []
        }
        self.job_type = job_test_utils.create_job_type(interface=job_interface)
        self.job = job_test_utils.create_job(job_type=self.job_type, data=job_data, results=job_results)

        # Attempt to stage related models
        self.job_exe = job_test_utils.create_job_exe(job=self.job)

        try:
            import recipe.test.utils as recipe_test_utils
            definition = {
                'version': '1.0',
                'input_data': [{
                    'name': 'Recipe Input',
                    'type': 'file',
                    'media_types': ['text/plain'],
                }],
                'jobs': [{
                    'name': 'Job 1',
                    'job_type': {
                        'name': self.job_type.name,
                        'version': self.job_type.version,
                    },
                    'recipe_inputs': [{
                        'recipe_input': 'Recipe Input',
                        'job_input': 'input_files',
                    }]
                }]
            }
            self.recipe_type = recipe_test_utils.create_recipe_type(definition=definition)
            self.recipe = recipe_test_utils.create_recipe(recipe_type=self.recipe_type)
            self.recipe_job = recipe_test_utils.create_recipe_job(recipe=self.recipe, job=self.job, job_name='Job 1')
        except:
            self.recipe_type = None
            self.recipe = None
            self.recipe_job = None

        try:
            import product.test.utils as product_test_utils
            self.product = product_test_utils.create_product(job_exe=self.job_exe, countries=[self.country])
        except:
            self.product = None

    def test_successful_empty(self):
        """Tests successfully calling the job details view with no data or results."""

        url = rest_util.get_url('/jobs/%i/' % self.job.id)
        response = self.client.generic('GET', url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)

        result = json.loads(response.content)
        self.assertEqual(result['job_type']['name'], self.job.job_type.name)
        self.assertEqual(result['job_type_rev']['job_type']['id'], self.job.job_type.id)

        self.assertEqual(len(result['inputs']), 3)
        for data_input in result['inputs']:
            self.assertIsNone(data_input['value'])

        self.assertEqual(len(result['outputs']), 2)
        for data_output in result['outputs']:
            self.assertIsNone(data_output['value'])

        if self.job_exe:
            self.assertEqual(result['job_exes'][0]['command_arguments'], self.job_exe.command_arguments)
        else:
            self.assertEqual(len(result['job_exes']), 0)

        if self.recipe:
            self.assertEqual(result['recipes'][0]['recipe_type']['name'], self.recipe.recipe_type.name)
        else:
            self.assertEqual(len(result['recipes']), 0)

    def test_successful_property(self):
        """Tests successfully calling the job details view for one input property."""
        self.job.job_type_rev.interface['input_data'] = [{
            'name': 'input_field',
            'type': 'property',
        }]
        self.job.job_type_rev.save()
        self.job.data['input_data'] = [{
            'name': 'input_field',
            'value': 10,
        }]
        self.job.save()

        url = rest_util.get_url('/jobs/%i/' % self.job.id)
        response = self.client.generic('GET', url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)

        result = json.loads(response.content)
        self.assertEqual(len(result['inputs']), 1)
        self.assertEqual(result['inputs'][0]['value'], 10)

    def test_successful_file(self):
        """Tests successfully calling the job details view for one input/output file."""
        self.job.job_type_rev.interface['input_data'] = [{
            'name': 'input_file',
            'type': 'file',
        }]
        self.job.job_type_rev.interface['output_data'] = [{
            'name': 'output_file',
            'type': 'file',
        }]
        self.job.job_type_rev.save()
        self.job.data['input_data'] = [{
            'name': 'input_file',
            'file_id': self.file.id,
        }]
        if self.product:
            self.job.results['output_data'] = [{
                'name': 'output_file',
                'file_id': self.product.id,
            }]
        self.job.save()

        url = rest_util.get_url('/jobs/%i/' % self.job.id)
        response = self.client.generic('GET', url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)

        result = json.loads(response.content)
        self.assertEqual(len(result['inputs']), 1)
        self.assertEqual(result['inputs'][0]['value']['id'], self.file.id)
        self.assertEqual(result['inputs'][0]['value']['countries'][0], self.country.iso3)

        if self.product:
            self.assertEqual(len(result['outputs']), 1)
            self.assertEqual(result['outputs'][0]['value']['id'], self.product.id)
            self.assertEqual(result['outputs'][0]['value']['countries'][0], self.country.iso3)

    def test_successful_files(self):
        """Tests successfully calling the job details view for multiple input/output files."""
        self.job.job_type_rev.interface['input_data'] = [{
            'name': 'input_files',
            'type': 'files',
        }]
        self.job.job_type_rev.interface['output_data'] = [{
            'name': 'output_files',
            'type': 'files',
        }]
        self.job.job_type_rev.save()
        self.job.data['input_data'] = [{
            'name': 'input_files',
            'file_ids': [self.file.id],
        }]
        if self.product:
            self.job.results['output_data'] = [{
                'name': 'output_files',
                'file_ids': [self.product.id],
            }]
        self.job.save()

        url = rest_util.get_url('/jobs/%i/' % self.job.id)
        response = self.client.generic('GET', url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)

        result = json.loads(response.content)
        self.assertEqual(len(result['inputs']), 1)
        self.assertEqual(result['inputs'][0]['value'][0]['id'], self.file.id)
        self.assertEqual(result['inputs'][0]['value'][0]['countries'][0], self.country.iso3)

        if self.product:
            self.assertEqual(len(result['outputs']), 1)
            self.assertEqual(result['outputs'][0]['value'][0]['id'], self.product.id)
            self.assertEqual(result['outputs'][0]['value'][0]['countries'][0], self.country.iso3)

    def test_superseded(self):
        """Tests successfully calling the job details view for superseded jobs."""

        job_data = {
            'input_data': []
        }
        job_results = {
            'output_data': []
        }
        new_job = job_test_utils.create_job(job_type=self.job_type, data=job_data, results=job_results,
                                            superseded_job=self.job, delete_superseded=False)

        # Make sure the original job was updated
        url = rest_util.get_url('/jobs/%i/' % self.job.id)
        response = self.client.generic('GET', url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)

        result = json.loads(response.content)
        self.assertTrue(result['is_superseded'])
        self.assertIsNone(result['root_superseded_job'])
        self.assertIsNotNone(result['superseded_by_job'])
        self.assertEqual(result['superseded_by_job']['id'], new_job.id)
        self.assertIsNotNone(result['superseded'])
        self.assertTrue(result['delete_superseded'])

        # Make sure the new new job has the expected relations
        url = rest_util.get_url('/jobs/%i/' % new_job.id)
        response = self.client.generic('GET', url)
        result = json.loads(response.content)

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        self.assertFalse(result['is_superseded'])
        self.assertIsNotNone(result['root_superseded_job'])
        self.assertEqual(result['root_superseded_job']['id'], self.job.id)
        self.assertIsNotNone(result['superseded_job'])
        self.assertEqual(result['superseded_job']['id'], self.job.id)
        self.assertIsNone(result['superseded'])
        self.assertFalse(result['delete_superseded'])

    def test_cancel_successful(self):
        """Tests successfully cancelling a job."""

        url = rest_util.get_url('/jobs/%i/' % self.job.id)
        data = {'status': 'CANCELED'}
        response = self.client.patch(url, json.dumps(data), 'application/json')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)

        result = json.loads(response.content)
        self.assertEqual(result['status'], 'CANCELED')

    def test_cancel_bad_param(self):
        """Tests cancelling a job with invalid arguments."""

        url = rest_util.get_url('/jobs/%i/' % self.job.id)
        data = {'foo': 'bar'}
        response = self.client.patch(url, json.dumps(data), 'application/json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.content)

    def test_cancel_bad_value(self):
        """Tests cancelling a job with an incorrect status."""

        url = rest_util.get_url('/jobs/%i/' % self.job.id)
        data = {'status': 'COMPLETED'}
        response = self.client.patch(url, json.dumps(data), 'application/json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.content)


class TestJobsUpdateView(TestCase):

    def setUp(self):
        django.setup()

        self.country = storage_test_utils.create_country()
        self.file = storage_test_utils.create_file(countries=[self.country])

        self.job_type1 = job_test_utils.create_job_type(name='test1', category='test-1')
        self.job1 = job_test_utils.create_job(
            job_type=self.job_type1, status='RUNNING',
            data={'input_data': [{'name': 'input_file', 'file_id': self.file.id}]},
        )

        self.job_type2 = job_test_utils.create_job_type(name='test2', category='test-2')
        self.job2 = job_test_utils.create_job(
            job_type=self.job_type2, status='PENDING',
            data={'input_data': [{'name': 'input_file', 'file_id': self.file.id}]},
        )

        self.job3 = job_test_utils.create_job(is_superseded=True)

    def test_successful(self):
        """Tests successfully calling the jobs view."""

        url = rest_util.get_url('/jobs/updates/')
        response = self.client.generic('GET', url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)

        result = json.loads(response.content)
        self.assertEqual(len(result['results']), 2)
        for entry in result['results']:
            expected = None
            if entry['id'] == self.job1.id:
                expected = self.job1
            elif entry['id'] == self.job2.id:
                expected = self.job2
            else:
                self.fail('Found unexpected result: %s' % entry['id'])
            self.assertEqual(entry['job_type']['name'], expected.job_type.name)
            self.assertEqual(len(entry['input_files']), 1)
            self.assertEqual(entry['input_files'][0]['id'], self.file.id)

    def test_status(self):
        """Tests successfully calling the jobs view filtered by status."""

        url = rest_util.get_url('/jobs/updates/?status=RUNNING')
        response = self.client.generic('GET', url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)

        result = json.loads(response.content)
        self.assertEqual(len(result['results']), 1)
        self.assertEqual(result['results'][0]['job_type']['id'], self.job1.job_type.id)

    def test_job_type_id(self):
        """Tests successfully calling the jobs view filtered by job type identifier."""

        url = rest_util.get_url('/jobs/updates/?job_type_id=%s' % self.job1.job_type.id)
        response = self.client.generic('GET', url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)

        result = json.loads(response.content)
        self.assertEqual(len(result['results']), 1)
        self.assertEqual(result['results'][0]['job_type']['id'], self.job1.job_type.id)

    def test_job_type_name(self):
        """Tests successfully calling the jobs view filtered by job type name."""

        url = rest_util.get_url('/jobs/updates/?job_type_name=%s' % self.job1.job_type.name)
        response = self.client.generic('GET', url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)

        result = json.loads(response.content)
        self.assertEqual(len(result['results']), 1)
        self.assertEqual(result['results'][0]['job_type']['name'], self.job1.job_type.name)

    def test_job_type_category(self):
        """Tests successfully calling the jobs view filtered by job type category."""

        url = rest_util.get_url('/jobs/updates/?job_type_category=%s' % self.job1.job_type.category)
        response = self.client.generic('GET', url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)

        result = json.loads(response.content)
        self.assertEqual(len(result['results']), 1)
        self.assertEqual(result['results'][0]['job_type']['category'], self.job1.job_type.category)

    def test_superseded(self):
        """Tests getting superseded jobs."""

        url = rest_util.get_url('/jobs/updates/?include_superseded=true')
        response = self.client.generic('GET', url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)

        result = json.loads(response.content)
        self.assertEqual(len(result['results']), 3)


class TestJobTypesView(TestCase):

    def setUp(self):
        django.setup()

        self.workspace = storage_test_utils.create_workspace()
        self.error = error_test_utils.create_error()
        self.job_type1 = job_test_utils.create_job_type(priority=2, mem=1.0, max_scheduled=1)
        self.job_type2 = job_test_utils.create_job_type(priority=1, mem=2.0, is_operational=False)
        self.job_type3 = job_test_utils.create_job_type(priority=1, mem=2.0, is_active=False)

    def test_successful(self):
        """Tests successfully calling the get all job types view."""

        url = rest_util.get_url('/job-types/')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)

        result = json.loads(response.content)
        self.assertEqual(len(result['results']), 2)
        for entry in result['results']:
            expected = None
            if entry['id'] == self.job_type1.id:
                expected = self.job_type1
            elif entry['id'] == self.job_type2.id:
                expected = self.job_type2
            else:
                self.fail('Found unexpected result: %s' % entry['id'])
            self.assertEqual(entry['name'], expected.name)
            self.assertEqual(entry['version'], expected.version)
            self.assertEqual(entry['max_scheduled'], expected.max_scheduled)

    def test_name(self):
        """Tests successfully calling the job types view filtered by job type name."""

        url = rest_util.get_url('/job-types/?name=%s' % self.job_type1.name)
        response = self.client.generic('GET', url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)

        result = json.loads(response.content)
        self.assertEqual(len(result['results']), 1)
        self.assertEqual(result['results'][0]['id'], self.job_type1.id)
        self.assertEqual(result['results'][0]['name'], self.job_type1.name)

    def test_category(self):
        """Tests successfully calling the job types view filtered by job type category."""

        url = rest_util.get_url('/job-types/?category=%s' % self.job_type1.category)
        response = self.client.generic('GET', url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)

        result = json.loads(response.content)
        self.assertEqual(len(result['results']), 1)
        self.assertEqual(result['results'][0]['id'], self.job_type1.id)
        self.assertEqual(result['results'][0]['category'], self.job_type1.category)

    def test_is_active(self):
        """Tests successfully calling the job types view filtered by inactive state."""

        url = rest_util.get_url('/job-types/?is_active=false')
        response = self.client.generic('GET', url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)

        result = json.loads(response.content)
        self.assertEqual(len(result['results']), 1)
        self.assertEqual(result['results'][0]['id'], self.job_type3.id)
        self.assertEqual(result['results'][0]['is_active'], self.job_type3.is_active)

    def test_is_operational(self):
        """Tests successfully calling the job types view filtered by operational state."""

        url = rest_util.get_url('/job-types/?is_operational=false')
        response = self.client.generic('GET', url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)

        result = json.loads(response.content)
        self.assertEqual(len(result['results']), 1)
        self.assertEqual(result['results'][0]['id'], self.job_type2.id)
        self.assertEqual(result['results'][0]['is_operational'], self.job_type2.is_operational)

    def test_sorting(self):
        """Tests custom sorting."""

        url = rest_util.get_url('/job-types/?order=priority')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)

        result = json.loads(response.content)
        self.assertEqual(len(result['results']), 2)
        self.assertEqual(result['results'][0]['id'], self.job_type2.id)
        self.assertEqual(result['results'][0]['name'], self.job_type2.name)
        self.assertEqual(result['results'][0]['version'], self.job_type2.version)

    def test_reverse_sorting(self):
        """Tests custom sorting in reverse."""

        url = rest_util.get_url('/job-types/?order=-mem_const_required')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)

        result = json.loads(response.content)
        self.assertEqual(len(result['results']), 2)
        self.assertEqual(result['results'][0]['id'], self.job_type2.id)
        self.assertEqual(result['results'][0]['name'], self.job_type2.name)
        self.assertEqual(result['results'][0]['version'], self.job_type2.version)

    def test_create(self):
        """Tests creating a new job type."""
        url = rest_util.get_url('/job-types/')
        json_data = {
            'name': 'job-type-post-test',
            'version': '1.0.0',
            'title': 'Job Type Post Test',
            'description': 'This is a test.',
            'priority': '1',
            'interface': {
                'version': '1.0',
                'command': 'test_cmd',
                'command_arguments': 'test_arg',
                'input_data': [],
                'output_data': [],
                'shared_resources': [],
            },
            'error_mapping': {
                'version': '1.0',
                'exit_codes': {
                    '1': self.error.name,
                },
            },
            'custom_resources': {
                'version': '1.0',
                'resources': {
                    'foo': 10.0
                }
            }
        }

        response = self.client.generic('POST', url, json.dumps(json_data), 'application/json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)

        job_type = JobType.objects.filter(name='job-type-post-test').first()

        results = json.loads(response.content)
        self.assertEqual(results['id'], job_type.id)
        self.assertEqual(results['priority'], 1)
        self.assertIsNotNone(results['error_mapping'])
        self.assertEqual(results['error_mapping']['exit_codes']['1'], self.error.name)
        self.assertEqual(results['custom_resources']['resources']['foo'], 10.0)
        self.assertIsNone(results['trigger_rule'])
        self.assertIsNone(results['max_scheduled'])

    def test_create_configuration(self):
        """Tests creating a new job type with a valid configuration."""
        url = rest_util.get_url('/job-types/')
        json_data = {
            'name': 'job-type-post-test-config',
            'version': '1.0.0',
            'title': 'Job Type Post Test',
            'description': 'This is a test.',
            'priority': '1',
            'interface': {
                'version': '1.4',
                'command': 'test_cmd',
                'command_arguments': 'test_arg ${DB_HOST}',
                'mounts': [{
                    'name': 'dted',
                    'path': '/some/path',
                    }],
                'settings': [{
                    'name': 'DB_HOST',
                    'required': True,
                }],
                'input_data': [],
                'output_data': [],
                'shared_resources': [],
            },
            'configuration': {
                'version': '2.0',
                'mounts': {
                    'dted': {'type': 'host',
                             'host_path': '/path/to/dted'}
                },
                'settings': {
                    'DB_HOST': 'scale'
                }
            },
            'error_mapping': {
                'version': '1.0',
                'exit_codes': {
                    '1': self.error.name,
                },
            },
            'custom_resources': {
                'version': '1.0',
                'resources': {
                    'foo': 10.0
                }
            }
        }

        response = self.client.generic('POST', url, json.dumps(json_data), 'application/json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)

        job_type = JobType.objects.filter(name='job-type-post-test-config').first()

        results = json.loads(response.content)
        self.assertEqual(results['id'], job_type.id)
        self.assertIsNotNone(results['configuration']['mounts'])
        self.assertIsNotNone(results['configuration']['settings'])

    def test_create_secrets(self):
        """Tests creating a new job type with secrets."""
        url = rest_util.get_url('/job-types/')
        json_data = {
            'name': 'job-type-post-test-secret',
            'version': '1.0.0',
            'title': 'Job Type Post Test',
            'description': 'This is a test.',
            'priority': '1',
            'interface': {
                'version': '1.4',
                'command': 'test_cmd',
                'command_arguments': 'test_arg ${DB_HOST}',
                'mounts': [{
                    'name': 'dted',
                    'path': '/some/path',
                    }],
                'settings': [{
                    'name': 'DB_HOST',
                    'required': True,
                    'secret': True,
                }],
                'input_data': [],
                'output_data': [],
                'shared_resources': [],
            },
            'configuration': {
                'version': '2.0',
                'mounts': {
                    'dted': {'type': 'host',
                             'host_path': '/path/to/dted'}
                },
                'settings': {
                    'DB_HOST': 'scale'
                }
            },
            'error_mapping': {
                'version': '1.0',
                'exit_codes': {
                    '1': self.error.name,
                },
            },
            'custom_resources': {
                'version': '1.0',
                'resources': {
                    'foo': 10.0
                }
            }
        }

        with patch.object(SecretsHandler, '__init__', return_value=None), \
          patch.object(SecretsHandler, 'set_job_type_secrets', return_value=None) as mock_set_secret:
            response = self.client.generic('POST', url, json.dumps(json_data), 'application/json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)

        job_type = JobType.objects.filter(name='job-type-post-test-secret').first()

        results = json.loads(response.content)
        self.assertEqual(results['id'], job_type.id)

        # Secrets sent to Vault
        secrets_name = '-'.join([json_data['name'], json_data['version']]).replace('.', '_')
        secrets = json_data['configuration']['settings']
        mock_set_secret.assert_called_once_with(secrets_name, secrets)

        #Secrets scrubbed from configuration on return
        self.assertEqual(results['configuration']['settings'], {})

    def test_create_max_scheduled(self):
        """Tests creating a new job type."""
        url = rest_util.get_url('/job-types/')
        json_data = {
            'name': 'job-type-max_scheduled-test',
            'version': '1.0.0',
            'title': 'Job Type max_scheduled Test',
            'description': 'This is a test.',
            'priority': '1',
            'max_scheduled': '42',
            'interface': {
                'version': '1.0',
                'command': 'test_cmd',
                'command_arguments': 'test_arg',
                'input_data': [],
                'output_data': [],
                'shared_resources': [],
            },
            'error_mapping': {
                'version': '1.0',
                'exit_codes': {
                    '1': self.error.name,
                },
            },
        }

        response = self.client.generic('POST', url, json.dumps(json_data), 'application/json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)

        job_type = JobType.objects.filter(name='job-type-max_scheduled-test').first()

        results = json.loads(response.content)
        self.assertEqual(results['id'], job_type.id)
        self.assertEqual(results['max_scheduled'], 42)

    def test_create_trigger(self):
        """Tests creating a new job type with a trigger rule."""
        url = rest_util.get_url('/job-types/')
        json_data = {
            'name': 'job-type-post-test',
            'version': '1.0.0',
            'title': 'Job Type Post Test',
            'description': 'This is a test.',
            'interface': {
                'version': '1.0',
                'command': 'test_cmd',
                'command_arguments': 'test_arg',
                'input_data': [{
                    'media_types': ['image/png'],
                    'type': 'file',
                    'name': 'input_file',
                }],
                'output_data': [],
                'shared_resources': [],
            },
            'trigger_rule': {
                'type': 'PARSE',
                'is_active': True,
                'configuration': {
                    'version': '1.0',
                    'condition': {
                        'media_type': 'image/png',
                        'data_types': [],
                    },
                    'data': {
                        'input_data_name': 'input_file',
                        'workspace_name': self.workspace.name,
                    }
                }
            }
        }

        response = self.client.generic('POST', url, json.dumps(json_data), 'application/json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)

        job_type = JobType.objects.filter(name='job-type-post-test').first()

        results = json.loads(response.content)
        self.assertEqual(results['id'], job_type.id)
        self.assertIsNotNone(results['interface'])
        self.assertDictEqual(results['error_mapping']['exit_codes'], {})
        self.assertEqual(results['trigger_rule']['type'], 'PARSE')

    def test_create_missing_mount(self):
        """Tests creating a new job type with a mount referenced in configuration but not interface."""
        url = rest_util.get_url('/job-types/')
        json_data = {
            'name': 'job-type-post-test-no-mount',
            'version': '1.0.0',
            'title': 'Job Type Post Test',
            'description': 'This is a test.',
            'priority': '1',
            'interface': {
                'version': '1.4',
                'command': 'test_cmd',
                'command_arguments': 'test_arg ${DB_HOST}',
                'mounts': [],
                'settings': [{
                    'name': 'DB_HOST',
                    'required': True,
                }],
                'input_data': [],
                'output_data': [],
                'shared_resources': [],
            },
            'configuration': {
                'version': '2.0',
                'mounts': {
                    'dted': {'type': 'host',
                             'host_path': '/path/to/dted'}
                },
                'settings': {
                    'DB_HOST': 'scale'
                }
            },
            'error_mapping': {
                'version': '1.0',
                'exit_codes': {
                    '1': self.error.name,
                },
            },
            'custom_resources': {
                'version': '1.0',
                'resources': {
                    'foo': 10.0
                }
            }
        }

        response = self.client.generic('POST', url, json.dumps(json_data), 'application/json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)

        job_type = JobType.objects.filter(name='job-type-post-test-no-mount').first()

        results = json.loads(response.content)
        self.assertEqual(results['id'], job_type.id)
        self.assertEqual(results['configuration']['mounts'], {})

    def test_create_missing_setting(self):
        """Tests creating a new job type with a setting referenced in configuration but not interface."""
        url = rest_util.get_url('/job-types/')
        json_data = {
            'name': 'job-type-post-test-no-setting',
            'version': '1.0.0',
            'title': 'Job Type Post Test',
            'description': 'This is a test.',
            'priority': '1',
            'interface': {
                'version': '1.4',
                'command': 'test_cmd',
                'command_arguments': 'test_arg',
                'mounts': [{
                    'name': 'dted',
                    'path': '/some/path',
                }],
                'settings': [],
                'input_data': [],
                'output_data': [],
                'shared_resources': [],
            },
            'configuration': {
                'version': '2.0',
                'mounts': {
                    'dted': {'type': 'host',
                             'host_path': '/path/to/dted'}
                },
                'settings': {
                    'DB_HOST': 'scale'
                }
            },
            'error_mapping': {
                'version': '1.0',
                'exit_codes': {
                    '1': self.error.name,
                },
            },
            'custom_resources': {
                'version': '1.0',
                'resources': {
                    'foo': 10.0
                }
            }
        }

        response = self.client.generic('POST', url, json.dumps(json_data), 'application/json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)

        job_type = JobType.objects.filter(name='job-type-post-test-no-setting').first()

        results = json.loads(response.content)
        self.assertEqual(results['id'], job_type.id)
        self.assertEqual(results['configuration']['settings'], {})

    def test_create_missing_other_setting(self):
        """Tests creating a new job type with a setting referenced in configuration but not interface."""
        url = rest_util.get_url('/job-types/')
        json_data = {
            'name': 'job-type-post-test-no-other-setting',
            'version': '1.0.0',
            'title': 'Job Type Post Test',
            'description': 'This is a test.',
            'priority': '1',
            'interface': {
                'version': '1.4',
                'command': 'test_cmd',
                'command_arguments': 'test_arg',
                'mounts': [{
                    'name': 'dted',
                    'path': '/some/path',
                }],
                'settings': [{
                    'name': 'DB_HOST',
                    'required': True,
                }],
                'input_data': [],
                'output_data': [],
                'shared_resources': [],
            },
            'configuration': {
                'version': '2.0',
                'mounts': {
                    'dted': {'type': 'host',
                             'host_path': '/path/to/dted'}
                },
                'settings': {
                    'DB_HOST': 'scale',
                    'setting': 'value'
                }
            },
            'error_mapping': {
                'version': '1.0',
                'exit_codes': {
                    '1': self.error.name,
                },
            },
            'custom_resources': {
                'version': '1.0',
                'resources': {
                    'foo': 10.0
                }
            }
        }

        good_setting = {
            'DB_HOST': 'scale'
        }

        response = self.client.generic('POST', url, json.dumps(json_data), 'application/json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)

        job_type = JobType.objects.filter(name='job-type-post-test-no-other-setting').first()

        results = json.loads(response.content)
        self.assertEqual(results['id'], job_type.id)
        self.assertEqual(results['configuration']['settings'], good_setting)

    def test_create_missing_param(self):
        """Tests creating a job type with missing fields."""
        url = rest_util.get_url('/job-types/')
        json_data = {
            'name': 'job-type-post-test',
        }

        response = self.client.generic('POST', url, json.dumps(json_data), 'application/json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.content)

    def test_create_bad_param(self):
        """Tests creating a job type with invalid type fields."""
        url = rest_util.get_url('/job-types/')
        json_data = {
            'name': 'job-type-post-test',
            'version': '1.0.0',
            'title': 'Job Type Post Test',
            'description': 'This is a test.',
            'priority': 'BAD',
            'interface': {
                'version': '1.0',
                'command': 'test_cmd',
                'command_arguments': 'test_arg',
                'input_data': [],
                'output_data': [],
                'shared_resources': [],
            },
        }

        response = self.client.generic('POST', url, json.dumps(json_data), 'application/json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.content)

    def test_create_bad_error(self):
        """Tests creating a new job type with an invalid error relationship."""
        url = rest_util.get_url('/job-types/')
        json_data = {
            'name': 'job-type-post-test',
            'version': '1.0.0',
            'description': 'This is a test.',
            'interface': {
                'version': '1.0',
                'command': 'test_cmd',
                'command_arguments': 'test_arg',
                'input_data': [],
                'output_data': [],
                'shared_resources': [],
            },
            'error_mapping': {
                'version': '1.0',
                'exit_codes': {
                    '1': 'BAD',
                },
            },
        }

        response = self.client.generic('POST', url, json.dumps(json_data), 'application/json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.content)

    def test_create_bad_custom_resources(self):
        """Tests creating a new job type with an invalid custom resources"""
        url = rest_util.get_url('/job-types/')
        json_data = {
            'name': 'job-type-post-test',
            'version': '1.0.0',
            'description': 'This is a test.',
            'interface': {
                'version': '1.0',
                'command': 'test_cmd',
                'command_arguments': 'test_arg',
                'input_data': [],
                'output_data': [],
                'shared_resources': [],
            },
            'custom_resources': {
                'version': '1.0',
                'resources': {
                    'foo': 'BAD',
                },
            },
        }

        response = self.client.generic('POST', url, json.dumps(json_data), 'application/json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.content)

    def test_create_bad_trigger_type(self):
        """Tests creating a new job type with an invalid trigger type."""
        url = rest_util.get_url('/job-types/')
        json_data = {
            'name': 'job-type-post-test',
            'version': '1.0.0',
            'description': 'This is a test.',
            'interface': {
                'version': '1.0',
                'command': 'test_cmd',
                'command_arguments': 'test_arg',
                'input_data': [],
                'output_data': [],
                'shared_resources': [],
            },
            'trigger_rule': {
                'type': 'BAD',
            }
        }

        response = self.client.generic('POST', url, json.dumps(json_data), 'application/json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.content)

    def test_create_bad_trigger_config(self):
        """Tests creating a new job type with an invalid trigger rule configuration."""
        url = rest_util.get_url('/job-types/')
        json_data = {
            'name': 'job-type-post-test',
            'version': '1.0.0',
            'description': 'This is a test.',
            'interface': {
                'version': '1.0',
                'command': 'test_cmd',
                'command_arguments': 'test_arg',
                'input_data': [],
                'output_data': [],
                'shared_resources': [],
            },
            'trigger_rule': {
                'type': 'PARSE',
                'configuration': {
                    'BAD': '1.0',
                }
            }
        }

        response = self.client.generic('POST', url, json.dumps(json_data), 'application/json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.content)


class TestJobTypeDetailsView(TestCase):

    def setUp(self):
        django.setup()

        self.interface = {
            'version': '1.4',
            'command': 'test_cmd',
            'command_arguments': 'test_arg',
            'env_vars': [],
            'mounts': [{
                'name': 'dted',
                'path': '/some/path',
                'required': True,
                'mode': 'ro'
            }],
            'settings': [{
                'name': 'DB_HOST',
                'required': True,
                'secret': False,
            }],
            'input_data': [],
            'output_data': [],
            'shared_resources': [],
        }

        self.configuration = {
            'version': '2.0',
            'mounts': {
                'dted': {
                    'type': 'host',
                    'host_path': '/path/to/dted',
                    },
            },
            'settings': {
                'DB_HOST': 'scale',
            },
        }

        self.error = error_test_utils.create_error(category='ALGORITHM')
        self.error_mapping = {
            'version': '1.0',
            'exit_codes': {
                '1': self.error.name,
            }
        }

        self.workspace = storage_test_utils.create_workspace()
        self.trigger_config = {
            'version': '1.0',
            'condition': {
                'media_type': 'text/plain',
            },
            'data': {
                'input_data_name': 'input_file',
                'workspace_name': self.workspace.name,
            }
        }
        self.trigger_rule = trigger_test_utils.create_trigger_rule(trigger_type='PARSE', is_active=True,
                                                                   configuration=self.trigger_config)

        self.job_type = job_test_utils.create_job_type(interface=self.interface, error_mapping=self.error_mapping,
                                                       trigger_rule=self.trigger_rule, max_scheduled=2,
                                                       configuration=self.configuration)
        self.error1 = error_test_utils.create_error()
        self.error2 = error_test_utils.create_error()

    def test_not_found(self):
        """Tests successfully calling the get job type details view with a job id that does not exist."""

        url = rest_util.get_url('/job-types/100/')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND, response.content)

    def test_successful(self):
        """Tests successfully calling the get job type details view."""

        url = rest_util.get_url('/job-types/%d/' % self.job_type.id)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)

        result = json.loads(response.content)
        self.assertTrue(isinstance(result, dict), 'result  must be a dictionary')
        self.assertEqual(result['id'], self.job_type.id)
        self.assertEqual(result['name'], self.job_type.name)
        self.assertEqual(result['version'], self.job_type.version)

        self.assertIsNotNone(result['interface'])
        self.assertIsNotNone(result['error_mapping'])
        self.assertIsNotNone(result['trigger_rule'])
        self.assertEqual(result['max_scheduled'], 2)
        self.assertEqual(len(result['errors']), 1)

        self.assertEqual(len(result['job_counts_6h']), 0)
        self.assertEqual(len(result['job_counts_12h']), 0)
        self.assertEqual(len(result['job_counts_24h']), 0)

    def test_successful_get_secrets(self):
        """Tests getting a job_type with associated secrets and extra mounts"""

        configuration = self.configuration.copy()
        configuration['mounts'] = {
            'dted': {
                'type': 'host',
                'host_path': '/path/to/dted',
            },
            'ref_data': {
                'type': 'host',
                'host_path': '/path/to/ref_data',
            }
        }
        configuration['settings'] = {
            'DB_HOST': 'scale',
            'OTHER_DB': 'other_scale'
        }

        interface = self.interface.copy()
        interface['settings'] = [{
            'name': 'DB_HOST',
            'required': True,
            'secret': True,
        }]

        new_job_type = job_test_utils.create_job_type(interface=interface, error_mapping=self.error_mapping,
                                                      trigger_rule=self.trigger_rule, max_scheduled=2,
                                                      configuration=configuration)

        url = rest_util.get_url('/job-types/%d/' % new_job_type.id)
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)

        result = json.loads(response.content)

        self.assertEqual(result['id'], new_job_type.id)
        self.assertEqual(result['name'], new_job_type.name)
        self.assertEqual(result['version'], new_job_type.version)

        # Check extra and secret settings removed
        self.assertEqual(result['configuration']['settings'], {})

        # Check extra mount removed
        self.assertEqual(result['configuration']['mounts'], self.configuration['mounts'])

    def test_successful_no_settings(self):
        """Tests getting a job_type with no settings in interface (but defined in configuration)"""

        configuration = self.configuration.copy()
        configuration['mounts'] = {
            'dted': {
                'type': 'host',
                'host_path': '/path/to/dted',
            },
            'ref_data': {
                'type': 'host',
                'host_path': '/path/to/ref_data',
            }
        }
        configuration['settings'] = {
            'DB_HOST': 'scale',
            'OTHER_DB': 'other_scale'
        }

        interface = self.interface.copy()
        interface['settings'] = []
        interface['mounts'] = []

        new_job_type = job_test_utils.create_job_type(interface=interface, error_mapping=self.error_mapping,
                                                      trigger_rule=self.trigger_rule, max_scheduled=2,
                                                      configuration=configuration)

        url = rest_util.get_url('/job-types/%d/' % new_job_type.id)
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)

        result = json.loads(response.content)

        self.assertEqual(result['id'], new_job_type.id)
        self.assertEqual(result['name'], new_job_type.name)
        self.assertEqual(result['version'], new_job_type.version)

        # Check extra settings removed
        self.assertEqual(result['configuration']['settings'], {})

        # Check extra mounts removed
        self.assertEqual(result['configuration']['mounts'], {})

    def test_edit_simple(self):
        """Tests editing only the basic attributes of a job type"""

        url = rest_util.get_url('/job-types/%d/' % self.job_type.id)
        json_data = {
            'title': 'Title EDIT',
            'description': 'Description EDIT',
        }
        response = self.client.generic('PATCH', url, json.dumps(json_data), 'application/json')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)

        result = json.loads(response.content)
        self.assertTrue(isinstance(result, dict), 'result  must be a dictionary')
        self.assertEqual(result['id'], self.job_type.id)
        self.assertEqual(result['title'], 'Title EDIT')
        self.assertEqual(result['description'], 'Description EDIT')
        self.assertEqual(result['revision_num'], 1)
        self.assertDictEqual(result['interface'], self.interface)
        self.assertDictEqual(result['error_mapping'], self.error_mapping)
        self.assertEqual(result['trigger_rule']['id'], self.trigger_rule.id)

    def test_edit_interface(self):
        """Tests editing the interface of a job type"""
        interface = self.interface.copy()
        interface['command'] = 'test_cmd_edit'

        url = rest_util.get_url('/job-types/%d/' % self.job_type.id)
        json_data = {
            'interface': interface,
        }
        response = self.client.generic('PATCH', url, json.dumps(json_data), 'application/json')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)

        result = json.loads(response.content)
        self.assertEqual(result['id'], self.job_type.id)
        self.assertEqual(result['title'], self.job_type.title)
        self.assertEqual(result['revision_num'], 2)
        self.assertEqual(result['interface']['command'], 'test_cmd_edit')
        self.assertEqual(result['trigger_rule']['id'], self.trigger_rule.id)

    def test_edit_configuration(self):
        """Tests editing the configuration of a job type"""
        configuration = self.configuration.copy()
        configuration['settings'] = {'DB_HOST': 'other_scale_db'}
        configuration['mounts'] = {
            'dted': {
                'type': 'host',
                'host_path': '/some/new/path'
                }
            }

        url = rest_util.get_url('/job-types/%d/' % self.job_type.id)
        json_data = {
            'configuration': configuration,
        }
        response = self.client.generic('PATCH', url, json.dumps(json_data), 'application/json')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)

        result = json.loads(response.content)
        self.assertEqual(result['id'], self.job_type.id)
        self.assertEqual(result['title'], self.job_type.title)
        self.assertEqual(result['revision_num'], 1)
        self.assertEqual(result['configuration']['settings'], {'DB_HOST': 'other_scale_db'})
        self.assertEqual(result['configuration']['mounts']['dted'], {'type': 'host', 'host_path': '/some/new/path'})
        self.assertEqual(result['trigger_rule']['id'], self.trigger_rule.id)

    def test_edit_configuration_secret(self):
        """Tests editing the configuration of a job type with secrets"""
        configuration = self.configuration.copy()

        interface = self.interface.copy()
        interface['settings'] = [{
            'name': 'DB_HOST',
            'required': True,
            'secret': True,
        }]

        url = rest_util.get_url('/job-types/%d/' % self.job_type.id)
        json_data = {
            'configuration': configuration,
            'interface': interface,
        }

        with patch.object(SecretsHandler, '__init__', return_value=None), \
          patch.object(SecretsHandler, 'set_job_type_secrets', return_value=None) as mock_set_secret:
            response = self.client.generic('PATCH', url, json.dumps(json_data), 'application/json')

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)

        result = json.loads(response.content)
        self.assertEqual(result['id'], self.job_type.id)
        self.assertEqual(result['title'], self.job_type.title)
        self.assertEqual(result['revision_num'], 2)
        self.assertEqual(result['trigger_rule']['id'], self.trigger_rule.id)

        # Secrets sent to Vault
        secrets_name = '-'.join([result['name'], result['version']]).replace('.', '_')
        secrets = configuration['settings']
        mock_set_secret.assert_called_once_with(secrets_name, secrets)

        #Secrets scrubbed from configuration on return
        self.assertEqual(result['configuration']['settings'], {})

    def test_edit_error_mapping(self):
        """Tests editing the error mapping of a job type"""
        error = error_test_utils.create_error(category='DATA')
        error_mapping = self.error_mapping.copy()
        error_mapping['exit_codes']['10'] = error.name

        url = rest_util.get_url('/job-types/%d/' % self.job_type.id)
        json_data = {
            'error_mapping': error_mapping,
        }
        response = self.client.generic('PATCH', url, json.dumps(json_data), 'application/json')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)

        result = json.loads(response.content)
        self.assertEqual(result['id'], self.job_type.id)
        self.assertEqual(result['title'], self.job_type.title)
        self.assertEqual(result['revision_num'], 1)
        self.assertEqual(result['error_mapping']['exit_codes']['10'], error.name)
        self.assertEqual(result['trigger_rule']['id'], self.trigger_rule.id)

    def test_edit_custom_resources(self):
        """Tests editing the custom resources of a job type"""

        url = rest_util.get_url('/job-types/%d/' % self.job_type.id)
        json_data = {
            'custom_resources': {'resources': {'foo': 10.0}},
        }
        response = self.client.generic('PATCH', url, json.dumps(json_data), 'application/json')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)

        result = json.loads(response.content)
        self.assertEqual(result['id'], self.job_type.id)
        self.assertEqual(result['title'], self.job_type.title)
        self.assertEqual(result['revision_num'], 1)
        self.assertEqual(result['custom_resources']['resources']['foo'], 10.0)

    def test_edit_trigger_rule(self):
        """Tests editing the trigger rule of a job type"""
        trigger_config = self.trigger_config.copy()
        trigger_config['condition']['media_type'] = 'application/json'

        url = rest_util.get_url('/job-types/%d/' % self.job_type.id)
        json_data = {
            'trigger_rule': {
                'type': 'PARSE',
                'configuration': trigger_config,
            }
        }
        response = self.client.generic('PATCH', url, json.dumps(json_data), 'application/json')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)

        result = json.loads(response.content)
        self.assertEqual(result['id'], self.job_type.id)
        self.assertEqual(result['title'], self.job_type.title)
        self.assertEqual(result['revision_num'], 1)
        self.assertIsNotNone(result['interface'])
        self.assertEqual(result['trigger_rule']['configuration']['condition']['media_type'], 'application/json')
        self.assertNotEqual(result['trigger_rule']['id'], self.trigger_rule.id)

    def test_edit_trigger_rule_pause(self):
        """Tests pausing the trigger rule of a job type"""
        trigger_config = self.trigger_config.copy()
        trigger_config['condition']['media_type'] = 'application/json'

        url = rest_util.get_url('/job-types/%d/' % self.job_type.id)
        json_data = {
            'trigger_rule': {
                'is_active': False,
            }
        }
        response = self.client.generic('PATCH', url, json.dumps(json_data), 'application/json')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)

        result = json.loads(response.content)
        self.assertEqual(result['id'], self.job_type.id)
        self.assertEqual(result['title'], self.job_type.title)
        self.assertEqual(result['revision_num'], 1)
        self.assertIsNotNone(result['interface'])
        self.assertEqual(result['trigger_rule']['is_active'], False)

    def test_edit_trigger_rule_remove(self):
        """Tests removing the trigger rule from a job type"""
        url = rest_util.get_url('/job-types/%d/' % self.job_type.id)
        json_data = {
            'trigger_rule': None,
        }
        response = self.client.generic('PATCH', url, json.dumps(json_data), 'application/json')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)

        result = json.loads(response.content)
        self.assertEqual(result['id'], self.job_type.id)
        self.assertEqual(result['title'], self.job_type.title)
        self.assertEqual(result['revision_num'], 1)
        self.assertIsNotNone(result['interface'])
        self.assertIsNone(result['trigger_rule'])

    def test_edit_interface_and_trigger_rule(self):
        """Tests editing the job type interface and trigger rule together"""
        interface = self.interface.copy()
        interface['command'] = 'test_cmd_edit'
        trigger_config = self.trigger_config.copy()
        trigger_config['condition']['media_type'] = 'application/json'

        url = rest_util.get_url('/job-types/%d/' % self.job_type.id)
        json_data = {
            'interface': interface,
            'trigger_rule': {
                'type': 'PARSE',
                'configuration': trigger_config,
            }
        }
        response = self.client.generic('PATCH', url, json.dumps(json_data), 'application/json')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)

        result = json.loads(response.content)
        self.assertEqual(result['id'], self.job_type.id)
        self.assertEqual(result['title'], self.job_type.title)
        self.assertEqual(result['revision_num'], 2)
        self.assertEqual(result['interface']['command'], 'test_cmd_edit')
        self.assertEqual(result['trigger_rule']['configuration']['condition']['media_type'], 'application/json')
        self.assertNotEqual(result['trigger_rule']['id'], self.trigger_rule.id)

    def test_edit_bad_interface(self):
        """Tests attempting to edit a job type using an invalid job interface"""
        interface = self.interface.copy()
        interface['version'] = 'BAD'

        url = rest_util.get_url('/job-types/%d/' % self.job_type.id)
        json_data = {
            'interface': interface,
        }
        response = self.client.generic('PATCH', url, json.dumps(json_data), 'application/json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.content)

    def test_edit_bad_error_mapping(self):
        """Tests attempting to edit a job type using an invalid error mapping"""
        error_mapping = self.error_mapping.copy()
        error_mapping['version'] = 'BAD'

        url = rest_util.get_url('/job-types/%d/' % self.job_type.id)
        json_data = {
            'error_mapping': error_mapping,
        }
        response = self.client.generic('PATCH', url, json.dumps(json_data), 'application/json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.content)

    def test_edit_bad_custom_resources(self):
        """Tests attempting to edit a job type using an invalid custom resources"""

        url = rest_util.get_url('/job-types/%d/' % self.job_type.id)
        json_data = {
            'custom_resources': {'version': '1.0', 'resources': {'foo': 'BAD'}},
        }
        response = self.client.generic('PATCH', url, json.dumps(json_data), 'application/json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.content)

    def test_edit_bad_trigger(self):
        """Tests attempting to edit a job type using an invalid trigger rule"""
        trigger_config = self.trigger_config.copy()
        trigger_config['version'] = 'BAD'

        url = rest_util.get_url('/job-types/%d/' % self.job_type.id)
        json_data = {
            'trigger_rule': {
                'type': 'PARSE',
                'configuration': trigger_config,
            }
        }
        response = self.client.generic('PATCH', url, json.dumps(json_data), 'application/json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.content)

    def test_edit_system_job_pause(self):
        """Tests pausing a system job"""

        url = rest_util.get_url('/job-types/%d/' % self.job_type.id)
        json_data = {
            'is_paused': True
        }
        self.job_type.is_system = True
        self.job_type.save()
        response = self.client.generic('PATCH', url, json.dumps(json_data), 'application/json')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)

        result = json.loads(response.content)
        self.assertEqual(result['id'], self.job_type.id)
        self.assertEqual(result['title'], self.job_type.title)
        self.assertEqual(result['revision_num'], 1)
        self.assertIsNotNone(result['interface'])
        self.assertEqual(result['is_paused'], True)

    def test_edit_system_job_invalid_field(self):
        """Tests updating an invalid system job field"""
        url = rest_util.get_url('/job-types/%d/' % self.job_type.id)
        json_data = {
            'title': 'Invalid title change'
        }
        self.job_type.is_system = True
        self.job_type.save()
        response = self.client.generic('PATCH', url, json.dumps(json_data), 'application/json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.content)


class TestJobTypesValidationView(TransactionTestCase):
    """Tests related to the job-types validation endpoint"""

    def setUp(self):
        django.setup()

        self.workspace = storage_test_utils.create_workspace()
        self.error = error_test_utils.create_error(category='ALGORITHM')

    def test_successful(self):
        """Tests validating a new job type."""
        json_data = {
            'name': 'job-type-test',
            'version': '1.0.0',
            'title': 'Job Type Test',
            'description': 'This is a test.',
            'interface': {
                'version': '1.0',
                'command': 'test_cmd',
                'command_arguments': 'test_arg',
                'input_data': [],
                'output_data': [],
                'shared_resources': [],
            },
            'error_mapping': {
                'version': '1.0',
                'exit_codes': {
                    '1': self.error.name,
                },
            },
            'custom_resources': {
                'version': '1.0',
                'resources': {
                    'foo': 50.0,
                },
            },
        }

        url = rest_util.get_url('/job-types/validation/')
        response = self.client.generic('POST', url, json.dumps(json_data), 'application/json')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)

        results = json.loads(response.content)
        self.assertDictEqual(results, {'warnings': []}, 'JSON result was incorrect')

    def test_successful_trigger(self):
        """Tests validating a new job type with a trigger."""
        json_data = {
            'name': 'job-type-test',
            'version': '1.0.0',
            'title': 'Job Type Test',
            'description': 'This is a test.',
            'interface': {
                'version': '1.0',
                'command': 'test_cmd',
                'command_arguments': 'test_arg',
                'input_data': [],
                'output_data': [],
                'shared_resources': [],
            },
            'trigger_rule': {
                'type': 'PARSE',
                'configuration': {
                    'version': '1.0',
                    'condition': {
                        'media_type': 'image/x-hdf5-image',
                        'data_types': [],
                    },
                    'data': {
                        'input_data_name': 'input_file',
                        'workspace_name': self.workspace.name,
                    }
                }
            }
        }

        url = rest_util.get_url('/job-types/validation/')
        response = self.client.generic('POST', url, json.dumps(json_data), 'application/json')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)

        results = json.loads(response.content)
        self.assertDictEqual(results, {'warnings': []}, 'JSON result was incorrect')

    def test_successful_configuration(self):
        """Tests validating a new job type with a valid configuration."""
        url = rest_util.get_url('/job-types/validation/')
        json_data = {
            'name': 'job-type-post-test-config',
            'version': '1.0.0',
            'title': 'Job Type Post Test',
            'description': 'This is a test.',
            'priority': '1',
            'interface': {
                'version': '1.4',
                'command': 'test_cmd',
                'command_arguments': 'test_arg ${DB_HOST}',
                'mounts': [{
                    'name': 'dted',
                    'path': '/some/path',
                    }],
                'settings': [{
                    'name': 'DB_HOST',
                    'required': True,
                }],
                'input_data': [],
                'output_data': [],
                'shared_resources': [],
            },
            'configuration': {
                'version': '2.0',
                'mounts': {
                    'dted': {'type': 'host',
                             'host_path': '/path/to/dted'}
                },
                'settings': {
                    'DB_HOST': 'scale'
                }
            },
            'error_mapping': {
                'version': '1.0',
                'exit_codes': {
                    '1': self.error.name,
                },
            },
            'custom_resources': {
                'version': '1.0',
                'resources': {
                    'foo': 10.0
                }
            }
        }

        response = self.client.generic('POST', url, json.dumps(json_data), 'application/json')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)

        results = json.loads(response.content)
        self.assertDictEqual(results, {'warnings': []}, 'JSON result was incorrect')

    def test_missing_mount(self):
        """Tests validating a new job type with a mount referenced in configuration but not interface."""
        url = rest_util.get_url('/job-types/validation/')
        json_data = {
            'name': 'job-type-post-test-no-mount',
            'version': '1.0.0',
            'title': 'Job Type Post Test',
            'description': 'This is a test.',
            'priority': '1',
            'interface': {
                'version': '1.4',
                'command': 'test_cmd',
                'command_arguments': 'test_arg ${DB_HOST}',
                'mounts': [],
                'settings': [{
                    'name': 'DB_HOST',
                    'required': True,
                }],
                'input_data': [],
                'output_data': [],
                'shared_resources': [],
            },
            'configuration': {
                'version': '2.0',
                'mounts': {
                    'dted': {'type': 'host',
                             'host_path': '/path/to/dted'}
                },
                'settings': {
                    'DB_HOST': 'scale'
                }
            },
            'error_mapping': {
                'version': '1.0',
                'exit_codes': {
                    '1': self.error.name,
                },
            },
            'custom_resources': {
                'version': '1.0',
                'resources': {
                    'foo': 10.0
                }
            }
        }

        response = self.client.generic('POST', url, json.dumps(json_data), 'application/json')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)

        results = json.loads(response.content)
        self.assertEqual(len(results['warnings']), 1)
        self.assertEqual(results['warnings'][0]['id'], 'mounts')

    def test_missing_setting(self):
        """Tests validating a new job type with a setting referenced in configuration but not interface."""
        url = rest_util.get_url('/job-types/validation/')
        json_data = {
            'name': 'job-type-post-test-no-setting',
            'version': '1.0.0',
            'title': 'Job Type Post Test',
            'description': 'This is a test.',
            'priority': '1',
            'interface': {
                'version': '1.4',
                'command': 'test_cmd',
                'command_arguments': 'test_arg',
                'mounts': [{
                    'name': 'dted',
                    'path': '/some/path',
                }],
                'settings': [],
                'input_data': [],
                'output_data': [],
                'shared_resources': [],
            },
            'configuration': {
                'version': '2.0',
                'mounts': {
                    'dted': {'type': 'host',
                             'host_path': '/path/to/dted'}
                },
                'settings': {
                    'DB_HOST': 'scale'
                }
            },
            'error_mapping': {
                'version': '1.0',
                'exit_codes': {
                    '1': self.error.name,
                },
            },
            'custom_resources': {
                'version': '1.0',
                'resources': {
                    'foo': 10.0
                }
            }
        }

        response = self.client.generic('POST', url, json.dumps(json_data), 'application/json')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)

        results = json.loads(response.content)
        self.assertEqual(len(results['warnings']), 1)
        self.assertEqual(results['warnings'][0]['id'], 'settings')

    def test_missing_other_setting(self):
        """Tests validating a new job type with a setting referenced in configuration but not interface."""
        url = rest_util.get_url('/job-types/validation/')
        json_data = {
            'name': 'job-type-post-test-no-other-setting',
            'version': '1.0.0',
            'title': 'Job Type Post Test',
            'description': 'This is a test.',
            'priority': '1',
            'interface': {
                'version': '1.4',
                'command': 'test_cmd',
                'command_arguments': 'test_arg',
                'mounts': [{
                    'name': 'dted',
                    'path': '/some/path',
                }],
                'settings': [{
                    'name': 'DB_HOST',
                    'required': True,
                }],
                'input_data': [],
                'output_data': [],
                'shared_resources': [],
            },
            'configuration': {
                'version': '2.0',
                'mounts': {
                    'dted': {'type': 'host',
                             'host_path': '/path/to/dted'}
                },
                'settings': {
                    'DB_HOST': 'scale',
                    'setting': 'value'
                }
            },
            'error_mapping': {
                'version': '1.0',
                'exit_codes': {
                    '1': self.error.name,
                },
            },
            'custom_resources': {
                'version': '1.0',
                'resources': {
                    'foo': 10.0
                }
            }
        }

        response = self.client.generic('POST', url, json.dumps(json_data), 'application/json')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)

        results = json.loads(response.content)
        self.assertEqual(len(results['warnings']), 1)
        self.assertEqual(results['warnings'][0]['id'], 'settings')

    def test_secret_setting(self):
        """Tests validating a new job type with a secret setting."""
        url = rest_util.get_url('/job-types/validation/')
        json_data = {
            'name': 'job-type-post-test-no-other-setting',
            'version': '1.0.0',
            'title': 'Job Type Post Test',
            'description': 'This is a test.',
            'priority': '1',
            'interface': {
                'version': '1.4',
                'command': 'test_cmd',
                'command_arguments': 'test_arg',
                'mounts': [{
                    'name': 'dted',
                    'path': '/some/path',
                }],
                'settings': [{
                    'name': 'DB_HOST',
                    'required': True,
                    'secret': True,
                }],
                'input_data': [],
                'output_data': [],
                'shared_resources': [],
            },
            'configuration': {
                'version': '2.0',
                'mounts': {
                    'dted': {'type': 'host',
                             'host_path': '/path/to/dted'}
                },
                'settings': {
                    'DB_HOST': 'some_secret_value',
                }
            },
            'error_mapping': {
                'version': '1.0',
                'exit_codes': {
                    '1': self.error.name,
                },
            },
            'custom_resources': {
                'version': '1.0',
                'resources': {
                    'foo': 10.0
                }
            }
        }

        response = self.client.generic('POST', url, json.dumps(json_data), 'application/json')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)

        results = json.loads(response.content)
        self.assertEqual(len(results['warnings']), 0)

    def test_bad_param(self):
        """Tests validating a new job type with missing fields."""
        url = rest_util.get_url('/job-types/validation/')
        json_data = {
            'name': 'job-type-post-test',
        }

        response = self.client.generic('POST', url, json.dumps(json_data), 'application/json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.content)

    def test_bad_error(self):
        """Tests validating a new job type with an invalid error relationship."""
        json_data = {
            'name': 'job-type-post-test',
            'version': '1.0.0',
            'description': 'This is a test.',
            'error_mapping': {
                'version': '1.0',
                'exit_codes': {
                    '1': 'BAD',
                },
            },
        }

        url = rest_util.get_url('/job-types/validation/')
        response = self.client.generic('POST', url, json.dumps(json_data), 'application/json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.content)

    def test_bad_custom_resources(self):
        """Tests validating a new job type with invalid custom resources."""
        json_data = {
            'name': 'job-type-post-test',
            'version': '1.0.0',
            'description': 'This is a test.',
            'custom_resources': {
                'version': '1.0',
                'resources': {
                    'foo': 'BAD',
                },
            },
        }

        url = rest_util.get_url('/job-types/validation/')
        response = self.client.generic('POST', url, json.dumps(json_data), 'application/json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.content)

    def test_warnings(self):
        """Tests validating a new job type with mismatched media type warnings."""
        json_data = {
            'name': 'job-type-post-test',
            'version': '1.0.0',
            'description': 'This is a test.',
            'interface': {
                'version': '1.0',
                'command': '/test.sh',
                'command_arguments': '${input_file}',
                'input_data': [{
                    'name': 'input_file',
                    'type': 'file',
                    'media_types': ['image/png'],
                }],
                'output_data': [],
            },
            'trigger_rule': {
                'type': 'PARSE',
                'configuration': {
                    'version': '1.0',
                    'condition': {
                        'media_type': 'text/plain',
                        'data_types': [],
                    },
                    'data': {
                        'input_data_name': 'input_file',
                        'workspace_name': self.workspace.name,
                    }
                }
            }
        }

        url = rest_util.get_url('/job-types/validation/')
        response = self.client.generic('POST', url, json.dumps(json_data), 'application/json')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)

        results = json.loads(response.content)
        self.assertEqual(len(results['warnings']), 1)
        self.assertEqual(results['warnings'][0]['id'], 'media_type')

    def test_bad_trigger_type(self):
        """Tests validating a new job type with an invalid trigger type."""
        json_data = {
            'name': 'job-type-post-test',
            'version': '1.0.0',
            'description': 'This is a test.',
            'interface': {
                'version': '1.0',
                'command': 'test_cmd',
                'command_arguments': 'test_arg',
                'input_data': [],
                'output_data': [],
                'shared_resources': [],
            },
            'trigger_rule': {
                'type': 'BAD',
            }
        }

        url = rest_util.get_url('/job-types/validation/')
        response = self.client.generic('POST', url, json.dumps(json_data), 'application/json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.content)

    def test_bad_trigger_config(self):
        """Tests validating a new job type with an invalid trigger rule configuration."""
        json_data = {
            'name': 'job-type-post-test',
            'version': '1.0.0',
            'description': 'This is a test.',
            'interface': {
                'version': '1.0',
                'command': 'test_cmd',
                'command_arguments': 'test_arg',
                'input_data': [],
                'output_data': [],
                'shared_resources': [],
            },
            'trigger_rule': {
                'type': 'PARSE',
                'configuration': {
                    'BAD': '1.0',
                }
            }
        }

        url = rest_util.get_url('/job-types/validation/')
        response = self.client.generic('POST', url, json.dumps(json_data), 'application/json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.content)


class TestJobTypesStatusView(TestCase):

    def setUp(self):
        django.setup()

        self.job_type1 = job_test_utils.create_job_type()

    def test_successful(self):
        """Tests successfully calling the status view."""
        job_test_utils.create_job(job_type=self.job_type1, status='COMPLETED')

        url = rest_util.get_url('/job-types/status/')
        response = self.client.generic('GET', url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)

        result = json.loads(response.content)
        self.assertEqual(len(result['results']), 1)
        self.assertEqual(result['results'][0]['job_type']['name'], self.job_type1.name)
        self.assertEqual(len(result['results'][0]['job_counts']), 1)
        self.assertEqual(result['results'][0]['job_counts'][0]['status'], 'COMPLETED')
        self.assertEqual(result['results'][0]['job_counts'][0]['count'], 1)

    def test_running(self):
        """Tests getting running jobs regardless of time filters."""
        old_timestamp = datetime.datetime(2015, 1, 1, tzinfo=utc)
        job_test_utils.create_job(job_type=self.job_type1, status='COMPLETED', last_status_change=old_timestamp)
        job_test_utils.create_job(job_type=self.job_type1, status='RUNNING', last_status_change=old_timestamp)

        new_timestamp = datetime.datetime(2015, 1, 10, tzinfo=utc)
        job_test_utils.create_job(job_type=self.job_type1, status='COMPLETED', last_status_change=new_timestamp)
        job_test_utils.create_job(job_type=self.job_type1, status='RUNNING', last_status_change=new_timestamp)

        url = rest_util.get_url('/job-types/status/?started=2015-01-05T00:00:00Z')
        response = self.client.generic('GET', url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)

        result = json.loads(response.content)
        self.assertEqual(len(result['results']), 1)
        self.assertEqual(len(result['results'][0]['job_counts']), 2)

        for entry in result['results'][0]['job_counts']:
            if entry['status'] == 'COMPLETED':
                self.assertEqual(entry['count'], 1)
            elif entry['status'] == 'RUNNING':
                self.assertEqual(entry['count'], 2)
            else:
                self.fail('Found unexpected job type count status: %s' % entry['status'])

    def test_is_operational(self):
        """Tests successfully calling the status view filtered by operational status."""
        job_test_utils.create_job(job_type=self.job_type1, status='COMPLETED')

        job_type2 = job_test_utils.create_job_type(is_operational=False)
        job_test_utils.create_job(job_type=job_type2, status='COMPLETED')

        url = rest_util.get_url('/job-types/status/?is_operational=false')
        response = self.client.generic('GET', url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)

        result = json.loads(response.content)
        self.assertEqual(len(result['results']), 1)
        self.assertEqual(result['results'][0]['job_type']['name'], job_type2.name)
        self.assertEqual(result['results'][0]['job_type']['is_operational'], job_type2.is_operational)
        self.assertEqual(len(result['results'][0]['job_counts']), 1)
        self.assertEqual(result['results'][0]['job_counts'][0]['count'], 1)


class TestJobTypesPendingView(TestCase):

    def setUp(self):
        django.setup()

        self.job = job_test_utils.create_job(status='PENDING')

    def test_successful(self):
        """Tests successfully calling the pending status view."""

        url = rest_util.get_url('/job-types/pending/')
        response = self.client.generic('GET', url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)

        result = json.loads(response.content)
        self.assertEqual(len(result['results']), 1)
        self.assertEqual(result['results'][0]['job_type']['name'], self.job.job_type.name)
        self.assertEqual(result['results'][0]['count'], 1)
        self.assertIsNotNone(result['results'][0]['longest_pending'])


class TestJobTypesRunningView(TestCase):

    def setUp(self):
        django.setup()

        self.job = job_test_utils.create_job(status='RUNNING')

    def test_successful(self):
        """Tests successfully calling the running status view."""

        url = rest_util.get_url('/job-types/running/')
        response = self.client.generic('GET', url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)

        result = json.loads(response.content)
        self.assertEqual(len(result['results']), 1)
        self.assertEqual(result['results'][0]['job_type']['name'], self.job.job_type.name)
        self.assertEqual(result['results'][0]['count'], 1)
        self.assertIsNotNone(result['results'][0]['longest_running'])


class TestJobTypesSystemFailuresView(TestCase):

    def setUp(self):
        django.setup()

        self.error = Error(name='Test Error', description='test')
        self.error.save()
        self.job = job_test_utils.create_job(status='FAILED', error=self.error)

    def test_successful(self):
        """Tests successfully calling the system failures view."""

        url = rest_util.get_url('/job-types/system-failures/')
        response = self.client.generic('GET', url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)

        result = json.loads(response.content)
        self.assertEqual(len(result['results']), 1)
        self.assertEqual(result['results'][0]['job_type']['name'], self.job.job_type.name)
        self.assertEqual(result['results'][0]['error']['name'], self.error.name)
        self.assertEqual(result['results'][0]['count'], 1)


class TestJobsWithExecutionView(TransactionTestCase):
    """An integration test of the Jobs with latest execution view"""

    def setUp(self):
        django.setup()

        self.job_type_1 = job_test_utils.create_job_type()
        self.job_type_2 = job_test_utils.create_job_type()

        self.job_1a = job_test_utils.create_job(job_type=self.job_type_1, status='COMPLETED')
        job_test_utils.create_job_exe(job=self.job_1a, status='FAILED')
        time.sleep(.01)
        job_test_utils.create_job_exe(job=self.job_1a, status='FAILED')
        time.sleep(.01)
        job_test_utils.create_job_exe(job=self.job_1a, status='COMPLETED')
        time.sleep(.01)
        self.last_run_1a = job_test_utils.create_job_exe(job=self.job_1a, status='RUNNING')

        self.job_1b = job_test_utils.create_job(job_type=self.job_type_1, status='FAILED')
        time.sleep(.01)
        self.last_run_1b = job_test_utils.create_job_exe(job=self.job_1b, status='FAILED')

        self.job_2a = job_test_utils.create_job(job_type=self.job_type_2, status='RUNNING')
        time.sleep(.01)
        job_test_utils.create_job_exe(job=self.job_2a, status='FAILED')
        time.sleep(.01)
        job_test_utils.create_job_exe(job=self.job_2a, status='FAILED')
        time.sleep(.01)
        job_test_utils.create_job_exe(job=self.job_2a, status='COMPLETED')
        time.sleep(.01)
        self.last_run_2a = job_test_utils.create_job_exe(job=self.job_2a, status='RUNNING')

        self.job_2b = job_test_utils.create_job(job_type=self.job_type_2, status='COMPLETED')
        time.sleep(.01)
        self.last_run_2b = job_test_utils.create_job_exe(job=self.job_2b, status='COMPLETED')

        self.job_3 = job_test_utils.create_job(is_superseded=True)

    def test_get_latest_job_exes(self):
        """Tests calling the jobs information service without a filter"""

        job_map = {
            self.job_1a.id: (self.job_1a, self.job_type_1, self.last_run_1a),
            self.job_1b.id: (self.job_1b, self.job_type_1, self.last_run_1b),
            self.job_2a.id: (self.job_2a, self.job_type_2, self.last_run_2a),
            self.job_2b.id: (self.job_2b, self.job_type_2, self.last_run_2b),
        }

        url = rest_util.get_url('/jobs/executions/')
        response = self.client.generic('GET', url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)

        results = json.loads(response.content)
        self.assertEqual(results['count'], 4)
        self.assertEqual(results['next'], None)
        self.assertEqual(results['previous'], None)

        job_ids = set()
        for job_entry in results['results']:
            self.assertFalse(job_entry['id'] in job_ids)
            job_ids.add(job_entry['id'])

            self.assertTrue(job_entry['id'] in job_map)
            expected_job, expected_type, expected_last_run = job_map[job_entry['id']]
            result_type_dict = job_entry['job_type']
            result_last_run_dict = job_entry['latest_job_exe']

            # Test a few values from the response
            self.assertEqual(expected_job.status, job_entry['status'])
            self.assertEqual(expected_job.priority, job_entry['priority'])
            self.assertEqual(expected_type.id, result_type_dict['id'])
            self.assertEqual(expected_type.name, result_type_dict['name'])
            self.assertEqual(expected_last_run.id, result_last_run_dict['id'])
            self.assertEqual(expected_last_run.job_exit_code, result_last_run_dict['job_exit_code'])

    def test_with_status_filter(self):
        url = rest_util.get_url('/jobs/executions/?status=COMPLETED')
        response = self.client.generic('GET', url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)

        results = json.loads(response.content)
        self.assertEqual(results['count'], 2)

        for job_entry in results['results']:
            self.assertTrue(job_entry['id'] in (self.job_1a.id, self.job_2b.id))

    def test_with_job_type_id_filter(self):
        url = rest_util.get_url('/jobs/executions/?job_type_id=%s' % self.job_type_1.id)
        response = self.client.generic('GET', url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)

        results = json.loads(response.content)
        self.assertEqual(results['count'], 2)

        for job_entry in results['results']:
            self.assertTrue(job_entry['id'] in (self.job_1a.id, self.job_1b.id))

    def test_with_job_type_name_filter(self):
        url = rest_util.get_url('/jobs/executions/?job_type_name=%s' % self.job_type_2.name)
        response = self.client.generic('GET', url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)

        results = json.loads(response.content)
        self.assertEqual(results['count'], 2)

        for job_entry in results['results']:
            self.assertTrue(job_entry['id'] in (self.job_2a.id, self.job_2b.id))

    def test_with_job_type_category_filter(self):
        url = rest_util.get_url('/jobs/executions/?job_type_category=%s' % self.job_type_2.category)
        response = self.client.generic('GET', url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)

        results = json.loads(response.content)
        self.assertEqual(results['count'], 2)

        for job_entry in results['results']:
            self.assertTrue(job_entry['id'] in (self.job_2a.id, self.job_2b.id))

    def test_error_category(self):
        """Tests successfully calling the jobs view filtered by error category."""

        error = error_test_utils.create_error(category='DATA')
        job = job_test_utils.create_job(error=error)

        url = rest_util.get_url('/jobs/executions/?error_category=%s' % error.category)
        response = self.client.generic('GET', url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)

        result = json.loads(response.content)
        self.assertEqual(len(result['results']), 1)
        self.assertEqual(result['results'][0]['id'], job.id)
        self.assertEqual(result['results'][0]['error']['category'], error.category)

    def test_superseded(self):
        """Tests getting superseded jobs."""

        url = rest_util.get_url('/jobs/executions/?include_superseded=true')
        response = self.client.generic('GET', url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)

        result = json.loads(response.content)
        self.assertEqual(len(result['results']), 5)


class TestJobExecutionsView(TransactionTestCase):

    def setUp(self):
        django.setup()

        self.job_type_1 = job_test_utils.create_job_type()
        self.job_type_2 = job_test_utils.create_job_type()

        self.job_1 = job_test_utils.create_job(job_type=self.job_type_1, status='COMPLETED')
        self.job_exe_1a = job_test_utils.create_job_exe(job=self.job_1, exe_num=1, status='FAILED')
        self.job_exe_1b = job_test_utils.create_job_exe(job=self.job_1, exe_num=2, status='FAILED')
        self.job_exe_1c = job_test_utils.create_job_exe(job=self.job_1, exe_num=3, status='FAILED')
        self.last_exe_1 = job_test_utils.create_job_exe(job=self.job_1, exe_num=4, status='RUNNING')

        self.job_2 = job_test_utils.create_job(job_type=self.job_type_1, status='FAILED')
        self.last_exe_2 = job_test_utils.create_job_exe(job=self.job_2, status='FAILED')

        job_3 = job_test_utils.create_job(job_type=self.job_type_2, status='RUNNING')
        job_test_utils.create_job_exe(job=job_3, status='FAILED')
        job_test_utils.create_job_exe(job=job_3, status='FAILED')
        job_test_utils.create_job_exe(job=job_3, status='COMPLETED')
        job_test_utils.create_job_exe(job=job_3, status='RUNNING')

        job_4 = job_test_utils.create_job(job_type=self.job_type_2, status='COMPLETED')
        job_test_utils.create_job_exe(job=job_4, status='COMPLETED')

    def test_get_job_executions(self):
        """This test checks to make sure there are 10 job executions."""
        url = rest_util.get_url('/job-executions/')
        response = self.client.generic('GET', url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)

        results = json.loads(response.content)
        job_exe_count = results['count']
        self.assertEqual(job_exe_count, 10)

    def test_get_job_executions_running_status(self):
        """This test checks to make sure there are 2 job executions running."""
        url = rest_util.get_url('/job-executions/?status=RUNNING')
        response = self.client.generic('GET', url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)

        results = json.loads(response.content)
        self.assertEqual(results['count'], 2)

    def test_get_job_executions_for_job_id(self):
        url = rest_util.get_url('/job-executions/?job_type_id=%s' % self.job_type_1.id)
        response = self.client.generic('GET', url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)

        results = json.loads(response.content)
        self.assertEqual(results['count'], 5)

        job_1_exe_list = (self.job_exe_1a.id, self.job_exe_1b.id, self.job_exe_1c.id, self.last_exe_1.id,
                          self.last_exe_2.id)
        for job_execution_entry in results['results']:
            job_exe_id = job_execution_entry['id']
            self.assertTrue(job_exe_id in job_1_exe_list)

    def test_get_job_executions_for_job_name(self):
        url = rest_util.get_url('/job-executions/?job_type_name=%s' % self.job_type_1.name)
        response = self.client.generic('GET', url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)

        results = json.loads(response.content)
        self.assertEqual(results['count'], 5)

        job_1_exe_list = (self.job_exe_1a.id, self.job_exe_1b.id, self.job_exe_1c.id, self.last_exe_1.id,
                          self.last_exe_2.id)
        for job_execution_entry in results['results']:
            job_exe_id = job_execution_entry['id']
            self.assertTrue(job_exe_id in job_1_exe_list)

    def test_get_job_executions_for_job_category(self):
        url = rest_util.get_url('/job-executions/?job_type_category=%s' % self.job_type_1.category)
        response = self.client.generic('GET', url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)

        results = json.loads(response.content)
        self.assertEqual(results['count'], 5)

        job_1_exe_list = (self.job_exe_1a.id, self.job_exe_1b.id, self.job_exe_1c.id, self.last_exe_1.id,
                          self.last_exe_2.id)
        for job_execution_entry in results['results']:
            job_exe_id = job_execution_entry['id']
            self.assertTrue(job_exe_id in job_1_exe_list)

    def test_no_tz(self):
        start_date_time = now() - datetime.timedelta(hours=1)
        end_date_time = now()
        url = rest_util.get_url('/job-executions/?started={0}&ended={1}'.format(start_date_time.isoformat(),
                                                                                end_date_time.isoformat()))
        response = self.client.generic('GET', url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.content)

    def test_get_job_execution_for_job_exe_id(self):
        url = rest_util.get_url('/job-executions/%d/' % self.job_exe_1a.id)
        response = self.client.generic('GET', url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)

        results = json.loads(response.content)
        self.assertEqual(results['id'], self.job_exe_1a.id)

    def test_get_job_execution_bad_id(self):
        url = rest_util.get_url('/job-executions/9999999/')
        response = self.client.generic('GET', url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND, response.content)


class TestJobExecutionSpecificLogView(TestCase):

    def setUp(self):
        django.setup()

    def test_bad_job_exe_id(self):
        url = rest_util.get_url('/job-executions/999999/logs/combined/')
        response = self.client.generic('GET', url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND, response.content)

    @patch('job.views.JobExecution.objects.get_logs')
    def test_combined_log_json_no_time(self, mock_get_logs):
        def new_get_log_json(include_stdout, include_stderr, since):
            self.assertTrue(include_stdout)
            self.assertTrue(include_stderr)
            self.assertIsNone(since)
            return {}, now()
        mock_get_logs.return_value.get_log_json.side_effect = new_get_log_json

        url = rest_util.get_url('/job-executions/999999/logs/combined/?format=json')
        response = self.client.generic('GET', url)

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        self.assertEqual(response.accepted_media_type, 'application/json')

    @patch('job.views.JobExecution.objects.get_logs')
    def test_combined_log_text_no_time(self, mock_get_logs):
        def new_get_log_text(include_stdout, include_stderr, since, html):
            self.assertTrue(include_stdout)
            self.assertTrue(include_stderr)
            self.assertIsNone(since)
            self.assertFalse(html)
            return 'hello', now()
        mock_get_logs.return_value.get_log_text.side_effect = new_get_log_text

        url = rest_util.get_url('/job-executions/999999/logs/combined/?format=txt')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        self.assertEqual(response.accepted_media_type, 'text/plain')

    @patch('job.views.JobExecution.objects.get_logs')
    def test_combined_log_html_no_time(self, mock_get_logs):
        def new_get_log_text(include_stdout, include_stderr, since, html):
            self.assertTrue(include_stdout)
            self.assertTrue(include_stderr)
            self.assertIsNone(since)
            self.assertTrue(html)
            return '<html>hello</html>', now()
        mock_get_logs.return_value.get_log_text.side_effect = new_get_log_text

        url = rest_util.get_url('/job-executions/999999/logs/combined/?format=html')
        response = self.client.generic('GET', url)

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        self.assertEqual(response.accepted_media_type, 'text/html')

    @patch('job.views.JobExecution.objects.get_logs')
    def test_combined_log_json_no_content(self, mock_get_logs):
        def new_get_log_json(include_stdout, include_stderr, since):
            self.assertTrue(include_stdout)
            self.assertTrue(include_stderr)
            self.assertIsNone(since)
            return None, now()
        mock_get_logs.return_value.get_log_json.side_effect = new_get_log_json

        url = rest_util.get_url('/job-executions/999999/logs/combined/?format=json')
        response = self.client.generic('GET', url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT, response.content)

    @patch('job.views.JobExecution.objects.get_logs')
    def test_stdout_log_html_no_time(self, mock_get_logs):
        def new_get_log_text(include_stdout, include_stderr, since, html):
            self.assertTrue(include_stdout)
            self.assertFalse(include_stderr)
            self.assertIsNone(since)
            self.assertTrue(html)
            return '<html>hello</html>', now()
        mock_get_logs.return_value.get_log_text.side_effect = new_get_log_text

        url = rest_util.get_url('/job-executions/999999/logs/stdout/?format=html')
        response = self.client.generic('GET', url)

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        self.assertEqual(response.accepted_media_type, 'text/html')

    @patch('job.views.JobExecution.objects.get_logs')
    def test_stderr_log_html_no_time(self, mock_get_logs):
        def new_get_log_text(include_stdout, include_stderr, since, html):
            self.assertFalse(include_stdout)
            self.assertTrue(include_stderr)
            self.assertIsNone(since)
            self.assertTrue(html)
            return '<html>hello</html>', now()
        mock_get_logs.return_value.get_log_text.side_effect = new_get_log_text

        url = rest_util.get_url('/job-executions/999999/logs/stderr/?format=html')
        response = self.client.generic('GET', url)

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        self.assertEqual(response.accepted_media_type, 'text/html')

    @patch('job.views.JobExecution.objects.get_logs')
    def test_combined_log_json_with_time(self, mock_get_logs):
        started = datetime.datetime(2016, 1, 1, tzinfo=utc)

        def new_get_log_json(include_stdout, include_stderr, since):
            self.assertTrue(include_stdout)
            self.assertTrue(include_stderr)
            self.assertEqual(since, started)
            return {}, now()
        mock_get_logs.return_value.get_log_json.side_effect = new_get_log_json

        url = rest_util.get_url('/job-executions/999999/logs/combined/?started=2016-01-01T00:00:00Z&format=json')
        response = self.client.generic('GET', url)

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        self.assertEqual(response.accepted_media_type, 'application/json')


class TestJobInputFilesView(TestCase):

    def setUp(self):

        # Create legacy test files
        self.f1_file_name = 'legacy_foo.bar'
        self.f1_last_modified = datetime.datetime(2016, 1, 2, tzinfo=utc)
        self.f1_source_started = datetime.datetime(2016, 1, 1, tzinfo=utc)
        self.f1_source_ended = datetime.datetime(2016, 1, 2, tzinfo=utc)
        self.file1 = storage_test_utils.create_file(file_name=self.f1_file_name, source_started=self.f1_source_started,
                                                    source_ended=self.f1_source_ended,
                                                    last_modified=self.f1_last_modified)

        self.f2_file_name = 'legacy_qaz.bar'
        self.f2_job_input = 'legacy_input_1'
        self.f2_last_modified = datetime.datetime(2016, 1, 3, tzinfo=utc)
        self.f2_source_started = datetime.datetime(2016, 1, 2, tzinfo=utc)
        self.f2_source_ended = datetime.datetime(2016, 1, 3, tzinfo=utc)
        self.file2 = storage_test_utils.create_file(file_name=self.f2_file_name, source_started=self.f2_source_started,
                                                    source_ended=self.f2_source_ended,
                                                    last_modified=self.f2_last_modified)

        job_interface = {
            'version': '1.0',
            'command': 'test_cmd',
            'command_arguments': 'test_arg',
            'input_data': [{
                'type': 'property',
                'name': 'input_field',
            }, {
                'type': 'file',
                'name': 'input_file',
            }, {
                'type': 'file',
                'name': 'other_input_file',
            }],
            'output_data': [{
                'type': 'file',
                'name': 'output_file',
            }, {
                'type': 'files',
                'name': 'output_files',
            }],
            'shared_resources': [],
        }

        job_data = {
            'input_data': [{
                'name': 'input_file',
                'file_id': self.file1.id,
            }, {
                'name': self.f2_job_input,
                'file_id': self.file2.id,
            }]
        }
        job_results = {
            'output_data': []
        }
        self.job_type = job_test_utils.create_job_type(interface=job_interface)
        self.legacy_job = job_test_utils.create_job(job_type=self.job_type, data=job_data, results=job_results)
        self.job = job_test_utils.create_job(job_type=self.job_type)

        # Create JobInputFile entry files
        self.f3_file_name = 'foo.bar'
        self.f3_last_modified = datetime.datetime(2016, 1, 11, tzinfo=utc)
        self.f3_source_started = datetime.datetime(2016, 1, 10, tzinfo=utc)
        self.f3_source_ended = datetime.datetime(2016, 1, 11, tzinfo=utc)
        self.file3 = job_test_utils.create_input_file(file_name=self.f3_file_name,
                                                      source_started=self.f3_source_started,
                                                      source_ended=self.f3_source_ended, job=self.job,
                                                      last_modified=self.f3_last_modified)

        self.f4_file_name = 'qaz.bar'
        self.f4_job_input = 'input_1'
        self.f4_last_modified = datetime.datetime(2016, 1, 12, tzinfo=utc)
        self.f4_source_started = datetime.datetime(2016, 1, 11, tzinfo=utc)
        self.f4_source_ended = datetime.datetime(2016, 1, 12, tzinfo=utc)
        self.file4 = job_test_utils.create_input_file(file_name=self.f4_file_name,
                                                      source_started=self.f4_source_started,
                                                      source_ended=self.f4_source_ended, job=self.job,
                                                      last_modified=self.f4_last_modified, job_input=self.f4_job_input)

    def test_successful_file(self):
        """Tests successfully calling the job input files view"""

        url = rest_util.get_url('/jobs/%i/input_files/' % self.job.id)
        response = self.client.generic('GET', url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)

        result = json.loads(response.content)
        results = result['results']
        self.assertEqual(len(results), 2)
        for result in results:
            self.assertTrue(result['id'] in [self.file3.id, self.file4.id])

    def test_legacy_successful_file(self):
        """Tests successfully calling the job input files view for legacy files with job_data"""

        url = rest_util.get_url('/jobs/%i/input_files/' % self.legacy_job.id)
        response = self.client.generic('GET', url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)

        result = json.loads(response.content)
        results = result['results']
        self.assertEqual(len(results), 2)
        for result in results:
            self.assertTrue(result['id'] in [self.file1.id, self.file2.id])

    def test_filter_job_input(self):
        """Tests successfully calling the job inputs files view with job_input string filtering"""

        url = rest_util.get_url('/jobs/%i/input_files/?job_input=%s' % (self.job.id, self.f4_job_input))
        response = self.client.generic('GET', url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)

        result = json.loads(response.content)
        results = result['results']
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['id'], self.file4.id)

    def test_legacy_filter_job_input(self):
        """Tests successfully calling the job inputs files view for legacy files with job_input string filtering"""

        url = rest_util.get_url('/jobs/%i/input_files/?job_input=%s' % (self.legacy_job.id, self.f2_job_input))
        response = self.client.generic('GET', url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)

        result = json.loads(response.content)
        results = result['results']
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['id'], self.file2.id)

    def test_file_name_successful(self):
        """Tests successfully calling the get files by name view"""

        url = rest_util.get_url('/jobs/%i/input_files/?file_name=%s' % (self.job.id, self.f3_file_name))
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)

        results = json.loads(response.content)
        result = results['results']
        self.assertEqual(len(result), 1)

        self.assertEqual(self.f3_file_name, result[0]['file_name'])
        self.assertEqual('2016-01-10T00:00:00Z', result[0]['source_started'])
        self.assertEqual(self.file3.id, result[0]['id'])

    def test_bad_file_name(self):
        """Tests unsuccessfully calling the get files by name view"""

        url = rest_util.get_url('/jobs/%i/input_files/?file_name=%s' % (self.job.id, 'not_a.file'))
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)

        results = json.loads(response.content)
        result = results['results']
        self.assertEqual(len(result), 0)

    def test_time_successful(self):
        """Tests unsuccessfully calling the get files by name view"""

        url = rest_util.get_url('/jobs/%i/input_files/?started=%s&ended=%s&time_field=%s' % (self.job.id,
                                                                                             '2016-01-10T00:00:00Z',
                                                                                             '2016-01-13T00:00:00Z',
                                                                                             'source'))
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)

        result = json.loads(response.content)
        results = result['results']
        self.assertEqual(len(results), 2)
        for result in results:
            self.assertTrue(result['id'] in [self.file3.id, self.file4.id])
