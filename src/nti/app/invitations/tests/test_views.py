#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# pylint: disable=protected-access,too-many-public-methods,arguments-differ

from hamcrest import is_
from hamcrest import is_not
from hamcrest import has_entry
from hamcrest import has_length
from hamcrest import assert_that
from hamcrest import contains_string
from nti.ntiids.ntiids import find_object_with_ntiid

does_not = is_not

import csv

import fudge

import simplejson as json

import tempfile

from zope import component
from zope import interface

from nti.app.invitations.invitations import JoinEntityInvitation

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.app.testing.webtest import TestApp

from nti.dataserver.tests import mock_dataserver

from nti.dataserver.users.communities import Community

from nti.dataserver.users.friends_lists import FriendsList

from nti.invitations.interfaces import IDisabledInvitation
from nti.invitations.interfaces import IInvitationsContainer
from nti.invitations.interfaces import InvitationValidationError

from nti.invitations.model import Invitation


class TestInvitationViews(ApplicationLayerTest):

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
                     extra_environ=self._make_extra_environ(
                         username='ossmkitty'),
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

            invitation = Invitation(receiver='ossmkitty',
                                    sender=self.default_username,
                                    code="disabled123")
            invitations.add(invitation)
            interface.alsoProvides(invitation, IDisabledInvitation)

        with mock_dataserver.mock_db_trans(self.ds):
            self._create_user()
            self._create_user(u'ossmkitty')

        # pylint: disable=no-member
        testapp = TestApp(self.app)
        kit_environ = self._make_extra_environ(username='ossmkitty')

        testapp.post('/dataserver2/users/ossmkitty/@@accept-invitation',
                     json.dumps({'invitation_codes': ['accepted']}),
                     extra_environ=kit_environ,
                     status=422)

        testapp.post('/dataserver2/users/ossmkitty/@@accept-invitation',
                     json.dumps({'invitation_codes': ['123456']}),
                     extra_environ=kit_environ,
                     status=422)

        mock_ai.is_callable().raises(ValueError())
        testapp.post('/dataserver2/users/ossmkitty/@@accept-invitation',
                     json.dumps({'invitation_codes': ['7890']}),
                     extra_environ=kit_environ,
                     status=422)
        testapp.post('/dataserver2/Invitations/7890/@@accept',
                     extra_environ=kit_environ,
                     status=422)

        mock_ai.is_callable().raises(InvitationValidationError())
        testapp.post('/dataserver2/users/ossmkitty/@@accept-invitation',
                     json.dumps({'invitation_codes': ['7890']}),
                     extra_environ=kit_environ,
                     status=422)

        testapp.post('/dataserver2/Invitations/7890/@@accept',
                     extra_environ=kit_environ,
                     status=422)

        mock_ai.is_callable().returns_fake()
        testapp.post('/dataserver2/Invitations/7890/@@accept',
                     extra_environ=kit_environ,
                     status=204)

        testapp.post('/dataserver2/Invitations/disabled123/@@accept',
                     extra_environ=kit_environ,
                     status=422)

    @WithSharedApplicationMockDS
    def test_valid_code_community(self):
        with mock_dataserver.mock_db_trans(self.ds):
            self._create_user()
            comm = Community.create_community(username=u'Bankai')
            invitation = JoinEntityInvitation()
            invitation.entity = comm.username
            invitation.receiver = self.default_username
            component.getUtility(IInvitationsContainer).add(invitation)
            code = invitation.code

        # pylint: disable=no-member
        testapp = TestApp(self.app)

        testapp.post('/dataserver2/users/sjohnson@nextthought.com/@@accept-invitations',
                     json.dumps({'code': code}),
                     extra_environ=self._make_extra_environ(),
                     status=204)

    @WithSharedApplicationMockDS
    def test_valid_code_friends(self):
        with mock_dataserver.mock_db_trans(self.ds):
            self._create_user()
            owner = self._create_user('ichigo')
            fl = FriendsList(u'MyList')
            fl.creator = owner
            owner.addContainedObject(fl)
            invitation = JoinEntityInvitation()
            invitation.entity = fl.NTIID
            invitation.receiver = self.default_username
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
            invitation = JoinEntityInvitation()
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

    @WithSharedApplicationMockDS
    def test_decline_invitations(self):
        with mock_dataserver.mock_db_trans(self.ds):
            self._create_user()
            comm = Community.create_community(username=u'Bankai')
            invitation = JoinEntityInvitation()
            invitation.entity = comm.username
            invitation.receiver = u'sjohnson@nextthought.com'
            component.getUtility(IInvitationsContainer).add(invitation)
            code = invitation.code

        # pylint: disable=no-member
        testapp = TestApp(self.app)
        testapp.post('/dataserver2/Invitations/%s/@@decline' % code,
                     extra_environ=self._make_extra_environ(),
                     status=204)

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_send_site_invitation(self):
        site_invitation_url = '/dataserver2/Invitations/@@send-site-invitation'
        with mock_dataserver.mock_db_trans(self.ds):
            # Send request with no data
            data = {}
            res = self.testapp.post_json(site_invitation_url,
                                         data,
                                         status=417)
            body = res.json_body
            assert_that(body[u'message'], is_(u'Invitations are a required field.'))
            assert_that(body[u'code'], is_(u'InvalidSiteInvitationData'))

            # Send request with missing fields
            data = {'invitations':
                [
                    {'realname': 'No Email'},
                    {'email': 'missingname@test.com'}
                ],
                'message': 'Missing Fields Test Case'}
            res = self.testapp.post_json(site_invitation_url,
                                         data,
                                         status=417)
            body = res.json_body
            assert_that(body[u'message'],
                        is_(u'The provided input is missing values or contains invalid email addresses.'))
            assert_that(body[u'code'], is_(u'InvalidSiteInvitationData'))
            assert_that(body[u'Warnings'], is_([u'Missing email for No Email.',
                                                u'Missing name for missingname@test.com.']))
            assert_that(body[u'InvalidEmails'], is_([]))

            # Send request with invalid email
            data = {'invitations':
                [
                    {'realname': 'Bad Email',
                     'email': 'bademail'}
                ],
                'message': 'Bad Email Test Case'
            }
            res = self.testapp.post_json(site_invitation_url,
                                         data,
                                         status=417)
            body = res.json_body
            assert_that(body[u'message'],
                        is_(u'The provided input is missing values or contains invalid email addresses.'))
            assert_that(body[u'code'], is_(u'InvalidSiteInvitationData'))
            assert_that(body[u'Warnings'], is_([]))
            assert_that(body[u'InvalidEmails'], is_([u'bademail']))

            # Send valid request
            data = {
                'invitations':
                    [
                        {'email': 'good@email.com',
                         'realname': 'Good Email'},
                        {'email': 'passing@test.com',
                         'realname': 'Passing Test'}
                    ],
                'message': 'Passing Test Case'
            }
            res = self.testapp.post_json(site_invitation_url,
                                         data,
                                         status=200)
            body = res.json_body
            assert_that(body['Items'], has_length(2))

    def _make_fake_csv(self, data):
        fake_csv = tempfile.NamedTemporaryFile(delete=False)
        fake_csv.name = 'test.csv'
        with open(fake_csv.name, 'w') as fake_csv:
            fake_writer = csv.writer(fake_csv)
            fake_writer.writerows(data)
        return fake_csv

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_send_site_csv_invitations(self):
        site_csv_invitation_url = '/dataserver2/Invitations/@@send-site-csv-invitation'
        with mock_dataserver.mock_db_trans(self.ds):
            # test invalid email
            data = [
                [u'bademail', u'Bad Email']
            ]
            self._make_fake_csv(data)
            res = self.testapp.post(site_csv_invitation_url,
                                    {'message': 'Test bad csv'},
                                    upload_files=[('csv', 'test.csv'), ],
                                    status=417)
            body = res.json_body
            assert_that(body[u'message'],
                        is_(u'The provided input is missing values or contains invalid email addresses.'))
            assert_that(body[u'code'], is_(u'InvalidSiteInvitationData'))
            assert_that(body[u'Warnings'], is_([]))
            assert_that(body[u'InvalidEmails'], is_([u'bademail']))

            # Test missing fields
            data = [
                [u'', u'No Email'],
                [u'missingname@test.com', u'']
            ]
            self._make_fake_csv(data)
            res = self.testapp.post(site_csv_invitation_url,
                                    {'message': 'Test bad csv'},
                                    upload_files=[('csv', 'test.csv'), ],
                                    status=417)
            body = res.json_body
            assert_that(body[u'message'],
                        is_(u'The provided input is missing values or contains invalid email addresses.'))
            assert_that(body[u'code'], is_(u'InvalidSiteInvitationData'))
            assert_that(body[u'Warnings'], is_([u'Missing email in line 1.',
                                                u'Missing name in line 2.']))
            assert_that(body[u'InvalidEmails'], is_([]))

            # Test good data
            data = [
                [u'test@email.com', u'Test Email'],
            ]
            self._make_fake_csv(data)
            res = self.testapp.post(site_csv_invitation_url,
                                    {'message': 'Test good csv'},
                                    upload_files=[('csv', 'test.csv'), ],
                                    status=200)
            body = res.json_body
            assert_that(body['Items'], has_length(1))

            # Test duplicate invite
            original_invitation = body['Items'][0]
            res = self.testapp.post(site_csv_invitation_url,
                                    {'message': 'Test repeat invitation'},
                                    upload_files=[('csv', 'test.csv'), ],
                                    status=200)
            body = res.json_body
            assert_that(body['Items'], has_length(1))
            invitation = body['Items'][0]
            assert_that(invitation, is_(original_invitation))
