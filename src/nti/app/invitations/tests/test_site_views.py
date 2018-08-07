#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
from __future__ import absolute_import
from __future__ import division

from hamcrest import assert_that
from hamcrest import is_
from hamcrest import is_not
from hamcrest import has_length

import csv
import tempfile

from zope import component

from nti.app.invitations.invitations import JoinEntityInvitation
from nti.app.invitations.invitations import JoinSiteInvitation

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.dataserver.tests import mock_dataserver

from nti.dataserver.users import User

from nti.externalization.interfaces import StandardExternalFields

from nti.invitations.interfaces import IInvitationsContainer

from nti.ntiids.oids import to_external_ntiid_oid

from nti.site.site import getSite

ITEMS = StandardExternalFields.ITEMS

__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)


class TestSiteInvitationViews(ApplicationLayerTest):

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

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_accept_site_invitation(self):
        # Create an invitation
        with mock_dataserver.mock_db_trans(self.ds):
            site_invitation = JoinSiteInvitation(code=u'Sunnyvale1',
                                                 receiver=u'ricky@tpb.net',
                                                 sender=u'sjohnson',
                                                 accepted=False,
                                                 target_site=getSite().__name__)

            assert_that(site_invitation.is_accepted(), is_(False))

            container = component.getUtility(IInvitationsContainer)

            assert_that(container, has_length(0))

            container.add(site_invitation)
            assert_that(container, has_length(1))

            inv_ntiid = to_external_ntiid_oid(site_invitation)

        # Accept the invitation with an anonymous user
        inv_url = '/dataserver2/Objects/%s/@@accept-site-invitation' % inv_ntiid
        self.testapp.get(inv_url,
                         status=204)
        with mock_dataserver.mock_db_trans(self.ds):
            container = component.getUtility(IInvitationsContainer)
            accepted_invitation = container.get(u'Sunnyvale1')
            assert_that(accepted_invitation.is_accepted(), is_(True))
            user = User.get_user(username=u'ricky@tpb.net')
            assert_that(user, is_not(None))

        # Check that an email already associated with a NT account fails creation
        with mock_dataserver.mock_db_trans(self.ds):
            site_invitation = JoinSiteInvitation(code=u'Sunnyvale2',
                                                 receiver=u'ricky@tpb.net',
                                                 sender=u'sjohnson',
                                                 accepted=False,
                                                 target_site=getSite().__name__)
            container = component.getUtility(IInvitationsContainer)
            container.add(site_invitation)
            inv_ntiid = to_external_ntiid_oid(site_invitation)

        inv_url = '/dataserver2/Objects/%s/@@accept-site-invitation' % inv_ntiid
        self.testapp.get(inv_url,
                         status=409)

        with mock_dataserver.mock_db_trans(self.ds):
            container = component.getUtility(IInvitationsContainer)
            accepted_invitation = container.get(u'Sunnyvale2')
            # assert_that(accepted_invitation.is_accepted(), is_(True))  # TODO don't doom tx

        # Check that an invitation for a different site than currently on cannot be accepted
        with mock_dataserver.mock_db_trans(self.ds):
            accepted_invitation.target_site = u'failure.com'

        self.testapp.get(inv_url,
                          status=409)

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_accept_site_invitation_with_code(self):
        inv_url = '/dataserver2/Invitations/@@accept-site-invitation'

        # Create an invitation
        with mock_dataserver.mock_db_trans(self.ds):
            site_invitation = JoinSiteInvitation(code=u'Sunnyvale1',
                                                 receiver=u'ricky@tpb.net',
                                                 sender=u'sjohnson',
                                                 accepted=False,
                                                 target_site=getSite().__name__)

            assert_that(site_invitation.is_accepted(), is_(False))
            container = component.getUtility(IInvitationsContainer)
            assert_that(container, has_length(0))
            container.add(site_invitation)
            assert_that(container, has_length(1))

        # Accept the invitation with an anonymous user
        self.testapp.get(inv_url,
                         params={'code': u'Sunnyvale1'},
                         status=204)
        with mock_dataserver.mock_db_trans(self.ds):
            container = component.getUtility(IInvitationsContainer)
            accepted_invitation = container.get(u'Sunnyvale1')
            assert_that(accepted_invitation.is_accepted(), is_(True))
            user = User.get_user(username=u'ricky@tpb.net')
            assert_that(user, is_not(None))

        # Check that an email already associated with a NT account fails creation
        with mock_dataserver.mock_db_trans(self.ds):
            site_invitation = JoinSiteInvitation(code=u'Sunnyvale2',
                                                 receiver=u'ricky@tpb.net',
                                                 sender=u'sjohnson',
                                                 accepted=False,
                                                 target_site=getSite().__name__)
            container = component.getUtility(IInvitationsContainer)
            container.add(site_invitation)

        self.testapp.get(inv_url,
                         params={u'code': u'Sunnyvale2'},
                         status=409)

        with mock_dataserver.mock_db_trans(self.ds):
            container = component.getUtility(IInvitationsContainer)
            accepted_invitation = container.get(u'Sunnyvale2')
            # assert_that(accepted_invitation.is_accepted(), is_(True))  # TODO don't doom tx

        # Check that an invitation for a different site than currently on cannot be accepted
        with mock_dataserver.mock_db_trans(self.ds):
            accepted_invitation.target_site = u'failure.com'

        self.testapp.get(inv_url,
                         params={u'code': u'Sunnyvale2'},
                         status=409)

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_pending_site_invitations(self):

        pending_url = '/dataserver2/Invitations/@@pending-site-invitations'

        with mock_dataserver.mock_db_trans(self.ds):
            site_invitation = JoinSiteInvitation(code=u'Sunnyvale1',
                                                 receiver=u'ricky@tpb.net',
                                                 sender=u'sjohnson',
                                                 accepted=False,
                                                 target_site=u'dataserver2')

            container = component.getUtility(IInvitationsContainer)
            container.add(site_invitation)

        # Generic test that there is one in there
        res = self.testapp.get(pending_url)
        body = res.json_body
        assert_that(body[ITEMS], has_length(1))

        with mock_dataserver.mock_db_trans(self.ds):
            site_invitation = JoinSiteInvitation(code=u'Sunnyvale2',
                                                 receiver=u'julian@tpb.net',
                                                 sender=u'sjohnson',
                                                 accepted=False,
                                                 target_site=u'exclude_me')

            container = component.getUtility(IInvitationsContainer)
            container.add(site_invitation)

        # Test that we only get them for the specified sites if passed
        res = self.testapp.get(pending_url,
                               {'site': 'dataserver2'})
        body = res.json_body
        assert_that(body[ITEMS], has_length(1))

        with mock_dataserver.mock_db_trans(self.ds):
            site_invitation = JoinEntityInvitation(code=u'Sunnyvale3',
                                                   receiver=u'lahey@tpb.net',
                                                   sender=u'sjohnson',
                                                   accepted=False)

            container = component.getUtility(IInvitationsContainer)
            container.add(site_invitation)

        res = self.testapp.get(pending_url)
        body = res.json_body
        assert_that(body[ITEMS], has_length(2))

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_generic_site_invitation(self):

        generic_url = '/dataserver2/Invitations/@@generic-site-invitation'

        # Basic test
        res = self.testapp.post_json(generic_url,
                                     {'code': 'generic_code'},
                                     status=200)
        body = res.json_body
        assert_that(body['code'], is_('generic_code'))

        # Test no code
        self.testapp.post_json(generic_url,
                               {},
                               status=417)

        # Test too long
        # Make a long string
        code = ''.join(['x' for _ in range(50)])
        self.testapp.post_json(generic_url,
                               {'code': code},
                               status=417)

        # Test accept (currently returns not implemented for the default case)
        self.testapp.get('/dataserver2/Invitations/@@accept-site-invitation',
                         params={'code': 'generic_code'},
                         status=501)
