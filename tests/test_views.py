#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_not
from hamcrest import has_entry
from hamcrest import assert_that
from hamcrest import contains_string
does_not = is_not

import anyjson as json

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.app.testing.webtest import TestApp

from nti.dataserver.tests import mock_dataserver

class TestApplicationInvitationUserViews(ApplicationLayerTest):

	@WithSharedApplicationMockDS
	def test_invalid_invitation_code(self):

		with mock_dataserver.mock_db_trans(self.ds):
			_ = self._create_user()

		testapp = TestApp(self.app)

		res = testapp.post('/dataserver2/users/sjohnson@nextthought.com/@@accept-invitations',
							json.dumps({'invitation_codes': ['foobar']}),
							extra_environ=self._make_extra_environ(),
							status=422)

		assert_that(res.json_body, has_entry('field', 'invitation_codes'))
		assert_that(res.json_body, has_entry('code', 'InvitationCodeError'))
		assert_that(res.json_body, has_entry('value', 'foobar'))
		assert_that(res.json_body, has_entry('message', contains_string('The invitation code is not valid.')))


	@WithSharedApplicationMockDS
	def test_wrong_user(self):
		
		with mock_dataserver.mock_db_trans(self.ds):
			self._create_user()
			self._create_user('ossmkitty')

		testapp = TestApp(self.app)

		testapp.post('/dataserver2/users/sjohnson@nextthought.com/@@accept-invitations',
					  json.dumps({'invitation_codes': ['foobar']}),
					  extra_environ=self._make_extra_environ(username='ossmkitty'),
					  status=403)

	@WithSharedApplicationMockDS
	def test_valid_code(self):

		with mock_dataserver.mock_db_trans(self.ds):
			self._create_user()

		testapp = TestApp(self.app)

		testapp.post('/dataserver2/users/sjohnson@nextthought.com/@@accept-invitations',
					  json.dumps({'invitation_codes': ['MATHCOUNTS']}),
					  extra_environ=self._make_extra_environ(),
					  status=204)

	@WithSharedApplicationMockDS
	def test_invalid_request(self):

		with mock_dataserver.mock_db_trans(self.ds):
			self._create_user()

		testapp = TestApp(self.app)

		testapp.post('/dataserver2/users/sjohnson@nextthought.com/@@accept-invitations',
					  json.dumps({'invitation_codes2': ['MATHCOUNTS']}),
					  extra_environ=self._make_extra_environ(),
					  status=400)
