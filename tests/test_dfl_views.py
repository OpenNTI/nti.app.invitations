#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import is_not
from hamcrest import has_item
from hamcrest import ends_with
from hamcrest import has_entry
from hamcrest import has_length
from hamcrest import assert_that
from hamcrest import has_entries
does_not = is_not

from six.moves import urllib_parse

import simplejson as json

from nti.app.invitations.views import REL_SEND_INVITATION
from nti.app.invitations.views import REL_TRIVIAL_DEFAULT_INVITATION_CODE

from nti.dataserver import users

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.app.testing.webtest import TestApp

from nti.dataserver.tests import mock_dataserver


class TestApplicationInvitationDFLViews(ApplicationLayerTest):

    @WithSharedApplicationMockDS
    def test_send_dfl_invitation(self):

        with mock_dataserver.mock_db_trans(self.ds):
            owner = self._create_user()
            owner_username = owner.username
            member_user = self._create_user(u'member@foo')
            member_user_username = member_user.username
            other_user = self._create_user(u'other@foo')
            other_user_username = other_user.username

            fl1 = users.DynamicFriendsList(username=u'Friends')
            fl1.creator = owner  # Creator must be set
            owner.addContainedObject(fl1)

            dfl_ntiid = fl1.NTIID

        testapp = TestApp(self.app)

        # The owner is the only one that has the link
        path = '/dataserver2/Objects/' + dfl_ntiid
        path = str(path)
        path = urllib_parse.quote(path)

        # And the owner is the only one that can fetch it
        res = testapp.post(path + '/@@' + str(REL_SEND_INVITATION),
                           json.dumps({'username': member_user_username}),
                           extra_environ=self._make_extra_environ(username=owner_username),
                           status=200)
        assert_that(res.json_body, has_entry('Items', has_length(1)))
        code = res.json_body['Items'][0]['code']

        res = testapp.get('/dataserver2/Invitations/%s' % code,
                          extra_environ=self._make_extra_environ(username=member_user_username),
                          status=200)
        assert_that(res.json_body, has_entry('Class', "JoinEntityInvitation"))
        assert_that(res.json_body,
                    has_entry('MimeType',
                              "application/vnd.nextthought.joinentityinvitation"))
        assert_that(res.json_body,
                    has_entry('Creator',
                              "sjohnson@nextthought.com"))
        assert_that(res.json_body,
                    has_entry('sender', "sjohnson@nextthought.com"))
        assert_that(res.json_body, has_entry('accepted', is_(False)))
        assert_that(res.json_body, has_entry('code', is_(code)))
        assert_that(res.json_body, has_entry('expiryTime', is_(0)))
        assert_that(res.json_body, has_entry('receiver', is_("member@foo")))

        testapp.get('/dataserver2/Invitations/%s' % code,
                    extra_environ=self._make_extra_environ(username=other_user_username),
                    status=403)

    @WithSharedApplicationMockDS
    def test_link_in_dfl(self):

        with mock_dataserver.mock_db_trans(self.ds):
            owner = self._create_user()
            owner_username = owner.username
            member_user = self._create_user(u'member@foo')
            member_user_username = member_user.username
            other_user = self._create_user(u'otheruser@foo')
            other_user_username = other_user.username

            fl1 = users.DynamicFriendsList(username=u'Friends')
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
        path = urllib_parse.quote(path)

        res = testapp.get(path, extra_environ=self._make_extra_environ())
        assert_that(res.json_body,
                    has_entry('Links',
                              has_item(has_entries('rel', REL_TRIVIAL_DEFAULT_INVITATION_CODE,
                                                   'href', ends_with('/@@' + REL_TRIVIAL_DEFAULT_INVITATION_CODE)))))

        res = testapp.get(path,
                          extra_environ=self._make_extra_environ(username=member_user_username))
        assert_that(res.json_body,
                    does_not(has_entry('Links',
                                       has_item(has_entries('rel', REL_TRIVIAL_DEFAULT_INVITATION_CODE,
                                                            'href', ends_with('/@@' + REL_TRIVIAL_DEFAULT_INVITATION_CODE))))))

        # And the owner is the only one that can fetch it
        testapp.get(path + '/@@' + str(REL_TRIVIAL_DEFAULT_INVITATION_CODE),
                    extra_environ=self._make_extra_environ(username=member_user_username),
                    status=403)

        res = testapp.get(path + '/@@' + str(REL_TRIVIAL_DEFAULT_INVITATION_CODE),
                          extra_environ=self._make_extra_environ())

        assert_that(res.json_body,
                    has_entry('invitation_code', is_(basestring)))

        # And the other user can accept it
        testapp.post('/dataserver2/users/otheruser@foo/@@accept-invitation',
                     json.dumps(
                         {'invitation_codes': [res.json_body['invitation_code']]}),
                     extra_environ=self._make_extra_environ(username=other_user_username))

        with mock_dataserver.mock_db_trans(self.ds):
            owner = users.User.get_user(owner_username)
            member_user = users.User.get_user(member_user_username)
            other_user = users.User.get_user(other_user_username)
            dfl = owner.getContainedObject(fl1_containerId, fl1_id)
            assert_that(list(dfl), is_([member_user, other_user]))
