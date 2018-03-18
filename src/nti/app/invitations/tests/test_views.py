#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# pylint: disable=protected-access,too-many-public-methods,arguments-differ

from hamcrest import is_not
from hamcrest import has_entry
from hamcrest import has_length
from hamcrest import assert_that
from hamcrest import contains_string
does_not = is_not

import fudge

import simplejson as json

from zope import component

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.app.testing.webtest import TestApp

from nti.dataserver.invitations import JoinCommunityInvitation

from nti.dataserver.tests import mock_dataserver

from nti.dataserver.users.communities import Community

from nti.invitations.interfaces import IInvitationsContainer
from nti.invitations.interfaces import InvitationValidationError

from nti.invitations.model import Invitation


class TestApplicationInvitationUserViews(ApplicationLayerTest):

    @WithSharedApplicationMockDS
    def test_invalid_invitation_code(self):

        with mock_dataserver.mock_db_trans(self.ds):
            self._create_user()

        # pylint: disable=no-member
        testapp = TestApp(self.app)

        testapp.get('/dataserver2/Invitations/foobar',
                    extra_environ=self._make_extra_environ(),
                    status=404)

        res = testapp.post('/dataserver2/users/sjohnson@nextthought.com/@@accept-invitation',
                           json.dumps({'code': 'foobar'}),
                           extra_environ=self._make_extra_environ(),
                           status=422)

        assert_that(res.json_body, has_entry('field', 'code'))
        assert_that(res.json_body, has_entry('value', 'foobar'))
        assert_that(res.json_body, has_entry('code', 'InvalidInvitationCode'))
        assert_that(res.json_body,
                    has_entry('message',
                              contains_string('Invalid invitation code.')))

    @WithSharedApplicationMockDS
    def test_wrong_user(self):

        with mock_dataserver.mock_db_trans(self.ds):
            self._create_user()
            self._create_user(u'ossmkitty')

        # pylint: disable=no-member
        testapp = TestApp(self.app)

        testapp.post('/dataserver2/users/sjohnson@nextthought.com/@@accept-invitation',
                     json.dumps({'invitation_codes': ['foobar']}),
                     extra_environ=self._make_extra_environ(username='ossmkitty'),
                     status=403)
        
    @WithSharedApplicationMockDS
    @fudge.patch('nti.app.invitations.views.accept_invitation')
    def test_validation_accept_invitation(self, mock_ai):

        with mock_dataserver.mock_db_trans(self.ds):
            invitations = component.getUtility(IInvitationsContainer)
            invitation = Invitation(receiver='ossmkitty',
                                    sender=self.default_username,
                                    accepted=True,
                                    code="accepted")
            invitations.add(invitation)
            
            invitation = Invitation(receiver='ichigo',
                                    sender=self.default_username,
                                    code="123456")
            invitations.add(invitation)
            
            invitation = Invitation(receiver='ossmkitty',
                                    sender=self.default_username,
                                    code="7890")
            invitations.add(invitation)
            
            
        with mock_dataserver.mock_db_trans(self.ds):
            self._create_user()
            self._create_user(u'ossmkitty')

        # pylint: disable=no-member
        testapp = TestApp(self.app)

        testapp.post('/dataserver2/users/ossmkitty/@@accept-invitation',
                     json.dumps({'invitation_codes': ['accepted']}),
                     extra_environ=self._make_extra_environ(username='ossmkitty'),
                     status=422)
        
        testapp.post('/dataserver2/users/ossmkitty/@@accept-invitation',
                     json.dumps({'invitation_codes': ['123456']}),
                     extra_environ=self._make_extra_environ(username='ossmkitty'),
                     status=422)
        
        mock_ai.is_callable().raises(ValueError())
        testapp.post('/dataserver2/users/ossmkitty/@@accept-invitation',
                     json.dumps({'invitation_codes': ['7890']}),
                     extra_environ=self._make_extra_environ(username='ossmkitty'),
                     status=422)
        testapp.post('/dataserver2/Invitations/7890/@@accept',
                     extra_environ=self._make_extra_environ(username='ossmkitty'),
                     status=422)

        mock_ai.is_callable().raises(InvitationValidationError())
        testapp.post('/dataserver2/users/ossmkitty/@@accept-invitation',
                     json.dumps({'invitation_codes': ['7890']}),
                     extra_environ=self._make_extra_environ(username='ossmkitty'),
                     status=422)
        
        testapp.post('/dataserver2/Invitations/7890/@@accept',
                     extra_environ=self._make_extra_environ(username='ossmkitty'),
                     status=422)
        
        mock_ai.is_callable().returns_fake()
        testapp.post('/dataserver2/Invitations/7890/@@accept',
                     extra_environ=self._make_extra_environ(username='ossmkitty'),
                     status=204)
        

    @WithSharedApplicationMockDS
    def test_valid_code(self):

        with mock_dataserver.mock_db_trans(self.ds):
            self._create_user()
            comm = Community.create_community(username=u'Bankai')
            invitation = JoinCommunityInvitation()
            invitation.entity = comm.username
            invitation.receiver = u'sjohnson@nextthought.com'
            component.getUtility(IInvitationsContainer).add(invitation)
            code = invitation.code

        # pylint: disable=no-member
        testapp = TestApp(self.app)

        testapp.post('/dataserver2/users/sjohnson@nextthought.com/@@accept-invitations',
                     json.dumps({'code': code}),
                     extra_environ=self._make_extra_environ(),
                     status=204)

    @WithSharedApplicationMockDS
    def test_pending_invitations(self):

        with mock_dataserver.mock_db_trans(self.ds):
            self._create_user()
            comm = Community.create_community(username=u'Bankai')
            invitation = JoinCommunityInvitation()
            invitation.entity = comm.username
            invitation.receiver = u'sjohnson@nextthought.com'
            component.getUtility(IInvitationsContainer).add(invitation)
            code = invitation.code

        # pylint: disable=no-member
        testapp = TestApp(self.app)
        res = testapp.get('/dataserver2/users/sjohnson@nextthought.com/@@pending-invitations',
                          extra_environ=self._make_extra_environ(),
                          status=200)
        assert_that(res.json_body, has_entry('Items', has_length(1)))

        testapp.post('/dataserver2/users/sjohnson@nextthought.com/@@decline-invitation',
                     json.dumps({'code': code}),
                     extra_environ=self._make_extra_environ(),
                     status=204)

        res = testapp.get('/dataserver2/users/sjohnson@nextthought.com/@@pending-invitations',
                          extra_environ=self._make_extra_environ(),
                          status=200)
        assert_that(res.json_body, has_entry('Items', has_length(0)))
