#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import is_not
from hamcrest import has_item
from hamcrest import ends_with
from hamcrest import has_entry
from hamcrest import assert_that
from hamcrest import has_entries
from hamcrest import contains_string
does_not = is_not

import urllib
import anyjson as json

from nti.app.invitations.views import REL_TRIVIAL_DEFAULT_INVITATION_CODE

from nti.dataserver import users

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

class TestApplicationInvitationDFLViews(ApplicationLayerTest):

	@WithSharedApplicationMockDS
	def test_link_in_dfl(self):
		with mock_dataserver.mock_db_trans(self.ds):
			owner = self._create_user()
			owner_username = owner.username
			member_user = self._create_user('member@foo')
			member_user_username = member_user.username
			other_user = self._create_user('otheruser@foo')
			other_user_username = other_user.username

			fl1 = users.DynamicFriendsList(username='Friends')
			fl1.creator = owner  # Creator must be set
			owner.addContainedObject(fl1)
			fl1.addFriend(member_user)

			dfl_ntiid = fl1.NTIID
			fl1_containerId = fl1.containerId
			fl1_id = fl1.id

			# Make sure not to access persistent objects after transaction
			del owner
			del member_user
			del other_user
			del fl1

		testapp = TestApp(self.app)

		# The owner is the only one that has the link
		path = '/dataserver2/Objects/' + dfl_ntiid
		path = str(path)
		path = urllib.quote(path)

		res = testapp.get(path, extra_environ=self._make_extra_environ())
		assert_that(res.json_body, has_entry('Links', has_item(has_entries('rel', REL_TRIVIAL_DEFAULT_INVITATION_CODE,
																		   'href', ends_with('/@@' + REL_TRIVIAL_DEFAULT_INVITATION_CODE)))))

		res = testapp.get(path, extra_environ=self._make_extra_environ(username=member_user_username))
		assert_that(res.json_body, does_not(has_entry('Links', has_item(has_entries('rel', REL_TRIVIAL_DEFAULT_INVITATION_CODE,
																					'href', ends_with('/@@' + REL_TRIVIAL_DEFAULT_INVITATION_CODE))))))


		# And the owner is the only one that can fetch it
		testapp.get(path + '/@@' + str(REL_TRIVIAL_DEFAULT_INVITATION_CODE),
					extra_environ=self._make_extra_environ(username=member_user_username),
					status=403)

		res = testapp.get(path + '/@@' + str(REL_TRIVIAL_DEFAULT_INVITATION_CODE),
						  extra_environ=self._make_extra_environ())

		assert_that(res.json_body, has_entry('invitation_code', is_(basestring)))

		# And the other user can accept it
		testapp.post('/dataserver2/users/otheruser@foo/@@accept-invitations',
					 json.dumps({'invitation_codes': [res.json_body['invitation_code']]}),
					 extra_environ=self._make_extra_environ(username=other_user_username))

		with mock_dataserver.mock_db_trans(self.ds):
			owner = users.User.get_user(owner_username)
			member_user = users.User.get_user(member_user_username)
			other_user = users.User.get_user(other_user_username)
			dfl = owner.getContainedObject(fl1_containerId, fl1_id)
			assert_that(list(dfl), is_([member_user, other_user]))
