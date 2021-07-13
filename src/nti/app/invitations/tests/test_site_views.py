#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
from __future__ import absolute_import
from __future__ import division

import contextlib

from collections import OrderedDict

import fudge

from hamcrest import is_
from hamcrest import not_
from hamcrest import not_none
from hamcrest import has_length
from hamcrest import has_entries
from hamcrest import starts_with
from hamcrest import assert_that
from hamcrest import contains_inanyorder
from hamcrest import contains_string

from six.moves import urllib_parse

import csv
import calendar
import tempfile

from datetime import datetime
from datetime import timedelta

from six.moves import StringIO

from zope import component

from zope.cachedescriptors.property import Lazy

from nti.app.invitations import SITE_INVITATION_MIMETYPE
from nti.app.invitations import SITE_ADMIN_INVITATION_MIMETYPE

from nti.app.invitations.interfaces import IInvitationSigner
from nti.app.invitations.interfaces import ISiteAdminInvitation

from nti.app.invitations.invitations import JoinEntityInvitation
from nti.app.invitations.invitations import SiteAdminInvitation
from nti.app.invitations.invitations import SiteInvitation

from nti.app.invitations.utils import get_invitation_url

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.app.testing.testing import ITestMailDelivery

from nti.appserver.policies.interfaces import ISitePolicyUserEventListener

from nti.common.url import safe_add_query_params

from nti.dataserver.tests import mock_dataserver

from nti.externalization.interfaces import StandardExternalFields

from nti.invitations.interfaces import IInvitationsContainer

from nti.ntiids.oids import to_external_ntiid_oid

ITEMS = StandardExternalFields.ITEMS

__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)


@contextlib.contextmanager
def modified_site_policy(ds, site_name, **kwargs):
    with mock_dataserver.mock_db_trans(ds, site_name=site_name):
        policy = component.queryUtility(ISitePolicyUserEventListener)
        original_values = {key: getattr(policy, key) for key in kwargs
                           if hasattr(policy, key)}
        for key, value in kwargs.items():
            setattr(policy, key, value)
    try:
        yield
    finally:
        with mock_dataserver.mock_db_trans(ds, site_name=site_name):
            policy = component.queryUtility(ISitePolicyUserEventListener)
            for key, value in original_values.items():
                setattr(policy, key, value)


class TestSiteInvitationViews(ApplicationLayerTest):
    # TODO it would be nice to assert that the request session state is what we
    # expect after the accept process

    @Lazy
    def invitations(self):
        return component.getUtility(IInvitationsContainer)

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_send_site_invitation(self):
        site_invitation_url = '/dataserver2/Invitations/@@send-site-invitation'
        # Send request with no data
        data = {}
        self.testapp.post_json(site_invitation_url,
                               data,
                               status=200)

        # Send request with missing fields
        data = {'invitations':
            [
                {'receiver_name': 'No Email'},
                {'receiver': 'missingname@test.com'}
            ],
            'message': 'Missing Fields Test Case'}
        res = self.testapp.post_json(site_invitation_url,
                                     data,
                                     status=417)
        body = res.json_body
        assert_that(body[u'message'],
                    is_(u'The provided input is missing values or contains invalid email addresses.'))
        assert_that(body[u'code'], is_(u'InvalidSiteInvitationData'))
        assert_that(body[u'Warnings'], is_([u'Missing email for No Email.']))
        assert_that(body[u'InvalidEmails'], is_([]))

        # Send request with invalid email
        data = {'invitations':
            [
                {'receiver_name': 'Bad Email',
                 'receiver': 'bademail'}
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
                    {'receiver': 'good@email.com',
                     'receiver_name': 'Good Email'},
                    {'receiver': 'passing@test.com',
                     'receiver_name': 'Passing Test'}
                ],
            'message': 'Passing Test Case'
        }
        res = self.testapp.post_json(site_invitation_url,
                                     data,
                                     status=200)
        body = res.json_body
        assert_that(body['Items'], has_length(2))

        mailer = component.getUtility(ITestMailDelivery)
        assert_that(mailer.queue, has_length(2))

    def _send_invitations(self, invitations):
        data = {
            'invitations': invitations,
            'message': 'Passing Test Case'
        }
        site_invitation_url = '/dataserver2/Invitations/@@send-site-invitation'
        res = self.testapp.post_json(site_invitation_url,
                                     data,
                                     status=200)

        return res

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_send_site_invitation_email(self):
        self._send_invitations([{
            'receiver': 'good@email.com',
            'receiver_name': 'Q @!%&! Bert'
        }])

        mailer = component.getUtility(ITestMailDelivery)
        assert_that(mailer.queue, has_length(1))

        # Text and html parts
        assert_that(mailer.queue[0].get_payload(), has_length(2))

        text_parts = [part for part in mailer.queue[0].get_payload()
                      if part['Content-Type'].startswith("text/plain")]
        assert_that(text_parts, has_length(1))

        text_body = text_parts[0].get_payload(decode=True)
        assert_that(text_body, contains_string("TO: Q @!%&! Bert\n"))

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_send_site_invitation_email_no_name(self):
        self._send_invitations([{'receiver': 'good@email.com'}])

        mailer = component.getUtility(ITestMailDelivery)
        assert_that(mailer.queue, has_length(1))

        # Text and html parts
        assert_that(mailer.queue[0].get_payload(), has_length(2))

        text_parts = [part for part in mailer.queue[0].get_payload()
                      if part['Content-Type'].startswith("text/plain")]
        assert_that(text_parts, has_length(1))

        text_body = text_parts[0].get_payload(decode=True)
        assert_that(text_body, contains_string("TO: good@email.com\n"))

    def _get_decoded_body(self, message, content_type):
        text_parts = [part for part in message.get_payload()
                      if part['Content-Type'].startswith(content_type)]
        assert_that(text_parts, has_length(1))

        decoded_body = text_parts[0].get_payload(decode=True)

        return decoded_body

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_send_site_invitation_email_alt_templates(self):
        new_template_location = b'nti.app.invitations.tests:templates/site_invitation_email'
        new_subject = u'Overridden subject'
        with modified_site_policy(
                self.ds, 'dataserver2',
                SITE_INVITATION_EMAIL_TEMPLATE_BASE_NAME=new_template_location,
                SITE_INVITATION_EMAIL_SUBJECT=new_subject):

            self._send_invitations([{
                'receiver': 'good@email.com',
                'receiver_name': 'Q Bert'
            }])

            mailer = component.getUtility(ITestMailDelivery)
            assert_that(mailer.queue, has_length(1))

            # Check overridden subject
            assert_that(mailer.queue[0].subject, is_(new_subject))

            # Text and html parts
            assert_that(mailer.queue[0].get_payload(), has_length(2))

            text_body = self._get_decoded_body(mailer.queue[0], "text/plain")
            assert_that(text_body, contains_string("OVERRIDDEN TEXT TEST TEMPLATE"))

            html_body = self._get_decoded_body(mailer.queue[0], "text/html")
            assert_that(html_body, contains_string("OVERRIDDEN HTML TEST TEMPLATE"))

    @WithSharedApplicationMockDS(testapp=True, users=True)
    @fudge.patch('nti.app.invitations.subscribers._site_policy')
    def test_send_site_invitation_email_no_policy(self, get_site_policy):
        get_site_policy.is_callable().returns(None)

        self._send_invitations([{
            'receiver': 'good@email.com',
            'receiver_name': 'Q Bert'
        }])

        mailer = component.getUtility(ITestMailDelivery)
        assert_that(mailer.queue, has_length(1))

    def _make_fake_csv(self, data):
        fake_csv = tempfile.NamedTemporaryFile(delete=False)
        fake_csv.name = 'test.csv'
        with open(fake_csv.name, 'w') as fake_csv:
            fake_writer = csv.writer(fake_csv)
            fake_writer.writerows(data)
        return fake_csv

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_send_site_csv_invitations(self):
        site_csv_invitation_url = '/dataserver2/Invitations/@@send-site-invitation'

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
            [u'bademail', u'No Email'],
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
        assert_that(body[u'Warnings'], has_length(0))
        assert_that(body[u'InvalidEmails'], is_([u'bademail']))

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

        # Test good data with BOM
        data = [
            ['test@email.com'.encode('utf-8-sig'), 'Test Email'.encode('utf-8-sig')],
        ]
        self._make_fake_csv(data)
        res = self.testapp.post(site_csv_invitation_url,
                                {'message': 'Test good csv'},
                                upload_files=[('csv', 'test.csv'), ],
                                status=200)
        body = res.json_body
        assert_that(body['Items'], has_length(1))

        # Test comma separated cells (no realname is ok)
        data = [
            ['test@email.com', 'Test, Email'],
            ['test2@email.com', 'Test No Comma'],
            ['test3@email.com', ',,,,,,,,,'],
            ['test4@email.com'],
            ['       ']
        ]
        self._make_fake_csv(data)
        res = self.testapp.post(site_csv_invitation_url,
                                {'message': 'Test good csv'},
                                upload_files=[('csv', 'test.csv'), ],
                                status=200)
        body = res.json_body
        assert_that(body['Items'], has_length(4))

    def _test_accept_site_invitation(self,
                                     create_invitation=True,
                                     code=None,
                                     scode=None,
                                     accepted=False,
                                     expired=False,
                                     failure=None,
                                     success=None,
                                     expected_status=302):
        effective_code = code
        if create_invitation:
            # Create an invitation
            with mock_dataserver.mock_db_trans(self.ds):
                site_invitation = SiteInvitation(code=u'Sunnyvale1',
                                                 receiver=u'ricky@tpb.net',
                                                 sender=u'sjohnson',
                                                 accepted=accepted,
                                                 expiryTime=0 if not expired else 1)

                assert_that(site_invitation.is_accepted(), is_(accepted))

                assert_that(self.invitations, has_length(0))

                self.invitations.add(site_invitation)
                assert_that(self.invitations, has_length(1))

                effective_code = site_invitation.code

        # Accept the invitation with an anonymous user
        params = dict()
        if scode:
            params['scode'] = scode
        elif effective_code:
            params['code'] = effective_code

        if success:
            params['success'] = success

        if failure:
            params['failure'] = failure

        inv_url = '/dataserver2/Invitations/@@accept-site-invitation'
        inv_url = safe_add_query_params(inv_url, params)

        self.testapp.set_authorization(None)
        return self.testapp.get(inv_url, status=expected_status)

    def _query_params(self, url):
        url_parts = list(urllib_parse.urlparse(url))
        # Query params are in index 4
        return OrderedDict(urllib_parse.parse_qsl(url_parts[4]))

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_accept_site_invitation(self):
        res = self._test_accept_site_invitation()
        assert_that(res.headers['Location'], contains_string('/NextThoughtWebApp'))
        assert_that(self._query_params(res.headers['Location']), has_length(0))

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_accept_site_invitation_bad_signature(self):
        res = self._test_accept_site_invitation(scode='abc.123',
                                                expected_status=422)

        assert_that(res.json_body, has_entries({
            "message": "Invalid invitation code.",
            "code": "InvalidInvitationCode"
        }))

    @WithSharedApplicationMockDS(testapp=True, users=True)
    @fudge.patch('nti.app.invitations.views.component.queryUtility')
    def test_accept_site_invitation_no_logon_provider(self, query_utility):
        # No logon provider returned
        query_utility.is_callable().returns(None)
        self._test_accept_site_invitation(expected_status=404)

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_accept_site_invitation_redirect_success(self):
        res = self._test_accept_site_invitation(success="/succeeded")
        assert_that(res.headers['Location'], starts_with("http://localhost/succeeded"))
        assert_that(self._query_params(res.headers['Location']), has_length(0))

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_accept_site_invitation_redirect_failure(self):
        res = self._test_accept_site_invitation(accepted=True,
                                                expected_status=303,
                                                failure="/failed")
        assert_that(res.headers['Location'], starts_with("http://localhost/failed"))
        self._assert_has_fail_params(res.headers['Location'],
                                     contains_string("no longer valid"))

    def _assert_has_fail_params(self, url, message_matcher):
        assert_that(self._query_params(url), has_entries({
            "failed": is_("true"),
            "error": message_matcher,
            "message": message_matcher,
        }))

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_accept_site_invitation_no_invitation(self):
        res = self._test_accept_site_invitation(create_invitation=False,
                                                code='should-not-exist',
                                                expected_status=303)
        assert_that(res.headers['Location'], contains_string('/login'))
        self._assert_has_fail_params(res.headers['Location'],
                                     contains_string("no longer valid"))

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_accept_site_invitation_accepted(self):
        res = self._test_accept_site_invitation(accepted=True,
                                                expected_status=303)
        assert_that(res.headers['Location'], contains_string('/login'))
        self._assert_has_fail_params(res.headers['Location'],
                                     contains_string("no longer valid"))

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_accept_site_invitation_expired(self):
        res = self._test_accept_site_invitation(expired=True,
                                                expected_status=303)
        assert_that(res.headers['Location'], contains_string('/login'))
        self._assert_has_fail_params(res.headers['Location'],
                                     contains_string("no longer valid"))

    def _test_fetch_invitation_info(self,
                                    init_code=True,
                                    create_invitation=True,
                                    accepted=False,
                                    require_matching_email=False,
                                    expected_status=None):
        if create_invitation:
            # Create an invitation
            with mock_dataserver.mock_db_trans(self.ds):
                site_invitation = SiteInvitation(code=u'Sunnyvale1',
                                                 receiver_name=u'Ricky Bobby',
                                                 receiver=u'ricky@tpb.net',
                                                 sender=u'sjohnson',
                                                 accepted=accepted,
                                                 require_matching_email=require_matching_email)

                assert_that(site_invitation.is_accepted(), is_(accepted))

                assert_that(self.invitations, has_length(0))

                self.invitations.add(site_invitation)
                assert_that(self.invitations, has_length(1))

                inv_ntiid = to_external_ntiid_oid(site_invitation)

            if init_code:
                # Accept the invitation with an anonymous user
                inv_url = '/dataserver2/Objects/%s/@@accept-site-invitation' % inv_ntiid
                self.testapp.set_authorization(None)
                self.testapp.get(inv_url,
                                 status=302)

        info_url = '/dataserver2/invitation-info'
        res = self.testapp.get(info_url, status=expected_status or 200)

        if expected_status == 200:
            assert_that(res.json_body, has_entries({
                "receiver_name": "Ricky Bobby",
                "receiver": "ricky@tpb.net",
                "require_matching_email": is_(require_matching_email)
            }))

            assert_that(res.json_body.keys(), not_(contains_inanyorder(
                'code',
                'original_receiver',
                'sender',
                'accepted'
            )))

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_fetch_invitation_info_valid(self):
        self._test_fetch_invitation_info()

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_fetch_invitation_info_valid_require_email_match(self):
        self._test_fetch_invitation_info(require_matching_email=True)

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_fetch_invitation_info_no_code(self):
        self._test_fetch_invitation_info(init_code=False, expected_status=404)

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_fetch_invitation_info_no_invitation(self):
        self._test_fetch_invitation_info(create_invitation=False,
                                         expected_status=404)

    @WithSharedApplicationMockDS(testapp=True, users=True)
    @fudge.patch('nti.app.invitations.views.IInvitationInfo')
    def test_fetch_invitation_info_no_adapt(self, i_info_adapter):
        i_info_adapter.is_callable().calls(lambda invitation: None)
        self._test_fetch_invitation_info(expected_status=404)

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_accept_site_invitation_with_code(self):
        inv_url = '/dataserver2/Invitations/@@accept-site-invitation'

        # Create an invitation
        with mock_dataserver.mock_db_trans(self.ds):
            site_invitation = SiteInvitation(code=u'Sunnyvale1',
                                             receiver=u'ricky@tpb.net',
                                             sender=u'sjohnson',
                                             acceptedTime=None)

            assert_that(site_invitation.is_accepted(), is_(False))
            assert_that(self.invitations, has_length(0))
            self.invitations.add(site_invitation)
            assert_that(self.invitations, has_length(1))

        # Accept the invitation with an anonymous user
        self.testapp.set_authorization(None)
        self.testapp.get(inv_url,
                         params={'code': u'Sunnyvale1'},
                         status=302)

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_accept_site_invitation_with_scode(self):
        # Create an invitation
        with mock_dataserver.mock_db_trans(self.ds):
            site_invitation = SiteInvitation(code=u'Sunnyvale1',
                                             receiver=u'ricky@tpb.net',
                                             sender=u'sjohnson',
                                             acceptedTime=None)

            assert_that(site_invitation.is_accepted(), is_(False))
            assert_that(self.invitations, has_length(0))
            self.invitations.add(site_invitation)
            assert_that(self.invitations, has_length(1))

            inv_url = get_invitation_url('', site_invitation)

        # Accept the invitation with an anonymous user
        self.testapp.set_authorization(None)
        self.testapp.get(inv_url, status=302)

        signed_params = dict(version='invalid')
        signer = component.getUtility(IInvitationSigner)
        params = {'scode': signer.encode(signed_params)}

        res = self.testapp.get("/dataserver2/Invitations/@@accept-site-invitation", params=params, status=422)

        assert_that(res.json_body['code'], is_(u'InvalidInvitationContentVersion'))

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_site_invitations(self):
        pending_url = '/dataserver2/Invitations/@@pending-site-invitations'

        with mock_dataserver.mock_db_trans(self.ds):
            site_invitation = SiteInvitation(code=u'Sunnyvale1',
                                             receiver=u'ricky@tpb.net',
                                             sender=u'sjohnson',
                                             acceptedTime=None)

            self.invitations.add(site_invitation)

        # Generic test that there is one in there
        res = self.testapp.get(pending_url)
        body = res.json_body
        assert_that(body[ITEMS], has_length(1))

        with mock_dataserver.mock_db_trans(self.ds):
            site_invitation = SiteInvitation(code=u'Sunnyvale2',
                                             receiver=u'julian@tpb.net',
                                             sender=u'sjohnson',
                                             acceptedTime=None,
                                             site=u'exclude_me')

            self.invitations.add(site_invitation)

        # Test that we only get them for the specified sites if passed
        res = self.testapp.get(pending_url,
                               {'site': 'dataserver2'})
        body = res.json_body
        assert_that(body[ITEMS], has_length(1))

        with mock_dataserver.mock_db_trans(self.ds):
            site_invitation = JoinEntityInvitation(code=u'Sunnyvale3',
                                                   receiver=u'lahey@tpb.net',
                                                   sender=u'sjohnson',
                                                   acceptedTime=None)

            self.invitations.add(site_invitation)

        res = self.testapp.get(pending_url,
                               {'site': 'exclude_me'})
        body = res.json_body
        assert_that(body[ITEMS], has_length(1))
        
    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_invitations(self):
        invitations_url = '/dataserver2/Invitations'

        now = datetime.utcnow()
        yesterday = now - timedelta(days=1)
        yesterday = calendar.timegm(yesterday.timetuple())
        tomorrow = now + timedelta(days=1)
        tomorrow = calendar.timegm(tomorrow.timetuple())
        with mock_dataserver.mock_db_trans(self.ds):
            # two pending, one per site
            site_invitation = SiteInvitation(code=u'Sunnyvale1',
                                             receiver=u'ricky1@tpb.net',
                                             sender=u'sjohnson',
                                             acceptedTime=None)

            self.invitations.add(site_invitation)
            site_invitation = SiteInvitation(code=u'Sunnyvale2',
                                             receiver=u'julian@tpb.net',
                                             sender=u'sjohnson',
                                             acceptedTime=None,
                                             site=u'exclude_me')

            self.invitations.add(site_invitation)
            # Three accepted, one per site and one expired but accepted
            site_invitation = SiteInvitation(code=u'Sunnyvale3',
                                             receiver=u'ricky2@tpb.net',
                                             sender=u'sjohnson2',
                                             acceptedTime=yesterday)
            self.invitations.add(site_invitation)
            site_invitation = SiteInvitation(code=u'Sunnyvale4',
                                             receiver=u'ricky3@tpb.net',
                                             sender=u'sjohnson2',
                                             acceptedTime=yesterday,
                                             site=u'exclude_me')
            self.invitations.add(site_invitation)
            site_invitation = SiteInvitation(code=u'Sunnyvale5',
                                             receiver=u'ricky4@tpb.net',
                                             sender=u'sjohnson2',
                                             acceptedTime=yesterday,
                                             expiryTime=yesterday)
            # Two expired
            self.invitations.add(site_invitation)
            site_invitation = SiteInvitation(code=u'Sunnyvale6',
                                             receiver=u'ricky5@tpb.net',
                                             sender=u'sjohnson2',
                                             acceptedTime=None,
                                             expiryTime=yesterday)
            self.invitations.add(site_invitation)
            site_invitation = SiteInvitation(code=u'Sunnyvale7',
                                             receiver=u'ricky6@tpb.net',
                                             sender=u'sjohnson2',
                                             acceptedTime=None,
                                             expiryTime=yesterday,
                                             site=u'exclude_me')
            self.invitations.add(site_invitation)
            # Expired in future
            site_invitation = SiteInvitation(code=u'Sunnyvale8',
                                             receiver=u'ricky7@tpb.net',
                                             sender=u'sjohnson2',
                                             acceptedTime=None,
                                             expiryTime=tomorrow)
            self.invitations.add(site_invitation)

        def _get_codes(type_filter=None, return_csv=False):
            headers = {'accept': str('application/json')}
            inv_url = invitations_url
            if type_filter:
                inv_url = '%s?type_filter=%s' % (invitations_url, type_filter)
            res = self.testapp.get(inv_url, headers=headers).json_body
            res = res[ITEMS]
            return [x['code'] for x in res]
                
        invite_codes = _get_codes()
        assert_that(invite_codes, contains_inanyorder('Sunnyvale1',
                                                      'Sunnyvale3',
                                                      'Sunnyvale5',
                                                      'Sunnyvale6',
                                                      'Sunnyvale8'))
        
        invite_codes = _get_codes('pending')
        assert_that(invite_codes, contains_inanyorder('Sunnyvale1',
                                                      'Sunnyvale8'))
        invite_codes = _get_codes('accepted')
        assert_that(invite_codes, contains_inanyorder('Sunnyvale3',
                                                      'Sunnyvale5'))
        invite_codes = _get_codes('expired')
        assert_that(invite_codes, contains_inanyorder('Sunnyvale6'))
        
        headers = {'accept': str('text/csv')}
        inv_url = '%s?type_filter=%s&sortOn=receiver' % (invitations_url, 'accepted')
        csv_res = self.testapp.get(inv_url, headers=headers).body
        csv_reader = csv.DictReader(StringIO(csv_res))
        csv_reader = tuple(csv_reader)
        assert_that(csv_reader, has_length(2))
        assert_that(csv_reader[0], has_entries('accepted time', not_none(),
                                               'sender username', 'sjohnson2',
                                               'expiration time', '',
                                               'site admin invitation', 'False',
                                               'target email', u'ricky2@tpb.net'))
        assert_that(csv_reader[1], has_entries('accepted time', not_none(),
                                               'sender username', 'sjohnson2',
                                               'expiration time', not_none(),
                                               'site admin invitation', 'False',
                                               'target email', u'ricky4@tpb.net'))
        
        inv_url = '%s?format=text/csv&sortOn=receiver' % (invitations_url,)
        csv_res = self.testapp.post(inv_url).body
        csv_reader = csv.DictReader(StringIO(csv_res))
        csv_reader = tuple(csv_reader)
        assert_that(csv_reader, has_length(5))
        
        codes = {'codes':['Sunnyvale6', 'Sunnyvale7']}
        inv_url = '%s?format=text/csv&sortOn=receiver' % (invitations_url,)
        csv_res = self.testapp.post(inv_url,
                                    params=codes,
                                    content_type='application/x-www-form-urlencoded')
        csv_reader = csv.DictReader(StringIO(csv_res.body))
        csv_reader = tuple(csv_reader)
        assert_that(csv_reader, has_length(1))
        assert_that(csv_reader[0], has_entries('accepted time', not_none(),
                                               'sender username', 'sjohnson2',
                                               'expiration time', not_none(),
                                               'site admin invitation', 'False',
                                               'target email', u'ricky5@tpb.net'))

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_generic_site_invitation(self):
        generic_url = '/dataserver2/Invitations/@@generic-site-invitation'

        with mock_dataserver.mock_db_trans(self.ds):
            assert_that(self.invitations, has_length(0))

        # Create a generic code
        res = self.testapp.post_json(generic_url,
                                     {'code': 'generic_code1'},
                                     status=200)
        body = res.json_body
        assert_that(body['code'], is_('generic_code1'))

        with mock_dataserver.mock_db_trans(self.ds):
            assert_that(self.invitations, has_length(1))

        # Test that the generic code is a singleton
        res = self.testapp.post_json(generic_url,
                                     {'code': 'generic_code2'},
                                     status=200)
        body = res.json_body
        assert_that(body['code'], is_('generic_code2'))

        with mock_dataserver.mock_db_trans(self.ds):
            assert_that(self.invitations, has_length(1))

        # Test PUT
        res = self.testapp.put_json(generic_url,
                                    {'code': 'generic_code3'},
                                    status=200)
        body = res.json_body
        assert_that(body['code'], is_('generic_code3'))

        with mock_dataserver.mock_db_trans(self.ds):
            assert_that(self.invitations, has_length(1))

        # Test delete
        self.testapp.delete(generic_url,
                            status=204)

        with mock_dataserver.mock_db_trans(self.ds):
            assert_that(self.invitations, has_length(0))

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

        # Test accept
        self.testapp.post_json(generic_url,
                               {'code': 'generic_code1'},
                               status=200)

        self.testapp.set_authorization(None)
        self.testapp.get('/dataserver2/Invitations/@@accept-site-invitation',
                         params={'code': 'generic_code1'},
                         status=302)

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_send_site_admin_invitation(self):
        # The core functionality of these views are covered above
        # We are verifying that the right invite is being created here
        site_invitation_url = '/dataserver2/Invitations/@@send-site-invitation'
        data = {
            'invitations':
                [
                    {'receiver': 'good@email.com',
                     'receiver_name': 'Good Email'},
                    {'receiver': 'passing@test.com',
                     'receiver_name': 'Passing Test'}
                ],
            'message': 'Passing Test Case',
            'mimeType': SITE_ADMIN_INVITATION_MIMETYPE
        }
        res = self.testapp.post_json(site_invitation_url,
                                     data,
                                     status=200)
        body = res.json_body
        assert_that(body['Items'], has_length(2))

        with mock_dataserver.mock_db_trans(self.ds):
            assert_that(self.invitations, has_length(2))
            for invitation in self.invitations.values():
                assert_that(ISiteAdminInvitation.providedBy(invitation), is_(True))

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_create_site_invitation(self):
        # The core functionality of these views are covered above
        # We are verifying that the email isn't sent here
        site_invitation_url = '/dataserver2/Invitations/@@create-site-invitation'
        data = {
            'invitations':
                [
                    {'receiver': 'good@email.com',
                     'receiver_name': 'Good Email'},
                ],
            'message': 'Passing Test Case',
            'mimeType': SITE_INVITATION_MIMETYPE
        }
        res = self.testapp.post_json(site_invitation_url,
                                     data,
                                     status=200)
        body = res.json_body
        assert_that(body['Items'], has_length(1))
        self.require_link_href_with_rel(body['Items'][0], 'redeem')

        mailer = component.getUtility(ITestMailDelivery)
        assert_that(mailer.queue, has_length(0))

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_pending_site_admin_invitations(self):
        pending_url = '/dataserver2/Invitations/@@pending-site-invitations'
        with mock_dataserver.mock_db_trans(self.ds):
            self._create_user(u'lahey', external_value={'email': u'lahey@tpb.net'})
            site_inv = SiteInvitation(receiver=u'ricky@tpb.net',
                                      sender=u'lahey')
            admin_inv = SiteAdminInvitation(receiver=u'julian@tpb.net',
                                            sender=u'lahey')
            self.invitations.add(site_inv)
            self.invitations.add(admin_inv)
        res = self.testapp.get(pending_url,
                               params={'exclude': SITE_INVITATION_MIMETYPE})
        body = res.json_body
        assert_that(body['Items'], has_length(1))

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_challenge_invitations(self):
        site_invitation_url = '/dataserver2/Invitations/@@send-site-invitation'
        data = {
            'invitations':
                [
                    {'receiver': 'good@email.com',
                     'receiver_name': 'Good Email'},
                    {'receiver': 'passing@test.com',
                     'receiver_name': 'Passing Test'}
                ],
            'message': 'Passing Test Case',
        }
        res = self.testapp.post_json(site_invitation_url,
                                     data,
                                     status=200)
        body = res.json_body
        assert_that(body['Items'], has_length(2))

        # Test resending
        data['invitations'].append({'receiver': 'new@email.com',
                                    'receiver_name': 'New Email'})

        res = self.testapp.post_json(site_invitation_url,
                                     data,
                                     status=200)
        body = res.json_body
        assert_that(body['Items'], has_length(3))

        # Test challenge to different endpoint
        site_invitation_url = '/dataserver2/Invitations/@@send-site-invitation'
        data['mimeType'] = SITE_ADMIN_INVITATION_MIMETYPE
        res = self.testapp.post_json(site_invitation_url,
                                     data,
                                     status=409)
        body = res.json_body
        assert_that(body[ITEMS], has_length(3))
        assert_that(body['code'], is_(u'UpdatePendingInvitations'))
        assert_that(body['message'], is_(u'3 pending invitations will be updated to a different role.'))

        # Test force
        url = body['Links'][0]['href']
        res = self.testapp.post_json(url,
                                     data,
                                     status=200)
        body = res.json_body
        assert_that(body['Items'], has_length(3))

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_delete_invitations(self):
        emails = []
        with mock_dataserver.mock_db_trans(self.ds):
            for i in range(5):
                email = "test%s@test.com" % i
                emails.append(email)
                inv = SiteInvitation(receiver=email,
                                     sender="sjohnson@nextthought.com")
                self.invitations.add(inv)

            assert_that(self.invitations, has_length(5))

        url = '/dataserver2/Invitations/@@delete-site-invitations'

        res = self.testapp.post_json(url,
                                     {'emails': emails},
                                     status=200)

        assert_that(res.json_body, has_length(5))
        with mock_dataserver.mock_db_trans(self.ds):
            assert_that(self.invitations, has_length(0))

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_sort_pending_invitations(self):
        emails = []
        with mock_dataserver.mock_db_trans(self.ds):
            for i in range(5):
                email = "%s@test.com" % i
                emails.append(email)
                inv = SiteInvitation(receiver=email,
                                     sender="sjohnson@nextthought.com")
                self.invitations.add(inv)

        url = '/dataserver2/Invitations/@@pending-site-invitations'
        res = self.testapp.get(url,
                               params={'sortOn': 'email'})
        for i, item in enumerate(res.json_body['Items']):
            assert_that(item['receiver'], is_(emails[i]))

        url = '/dataserver2/Invitations/@@pending-site-invitations'
        res = self.testapp.get(url,
                               params={'sortOn': 'created_time'})
        for i, item in enumerate(res.json_body['Items']):
            assert_that(item['receiver'], is_(emails[i]))

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_filter_pending_invitations(self):
        emails = []
        with mock_dataserver.mock_db_trans(self.ds):
            for i in range(15):
                email = "%s@test.com" % i
                emails.append(email)
                inv = SiteInvitation(receiver=email,
                                     sender="sjohnson@nextthought.com")
                self.invitations.add(inv)

        url = '/dataserver2/Invitations/@@pending-site-invitations'
        res = self.testapp.get(url,
                               params={'filterOn': 'receiver',
                                       'filter': '1'})

        assert_that(res.json_body['Items'], has_length(6))
        assert_that(res.json_body['Total'], is_(15))

        url = '/dataserver2/Invitations/@@pending-site-invitations'
        res = self.testapp.get(url,
                               params={'filterOn': 'receiver',
                                       'filter': '11@test.com'})
        assert_that(res.json_body['Items'], has_length(1))
        assert_that(res.json_body['Total'], is_(15))

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_send_to_existing_email(self):
        with mock_dataserver.mock_db_trans(self.ds):
            self._create_user(u'lahey', external_value={'email': u'lahey@tpb.net'})
        site_invitation_url = '/dataserver2/Invitations/@@send-site-invitation'
        data = {
            'invitations':
                [
                    {'receiver': 'lahey@tpb.net',
                     'receiver_name': 'Lahey'},
                ],
        }
        res = self.testapp.post_json(site_invitation_url,
                                     data,
                                     status=409)
        body = res.json_body
        assert_that(body['Items'], has_length(1))

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_existing_user_accept(self):
        with mock_dataserver.mock_db_trans(self.ds):
            user = self._create_user(u'lahey', external_value={'email': u'lahey@tpb.net'})
            inv = SiteInvitation(receiver=u'lahey@tpb.net',
                                 sender=u'lahey',
                                 code=u'Sunnyvale',
                                 target_site='dataserver2')
            self.invitations.add(inv)
            extra_environ = self._make_extra_environ(user=user.username, update_request=True)

        site_invitation_url = '/dataserver2/Invitations/@@accept-site-invitation'

        self.testapp.get(site_invitation_url,
                         params={'code': u'Sunnyvale'},
                         extra_environ=extra_environ,
                         status=302)

        with mock_dataserver.mock_db_trans(self.ds):
            inv = SiteInvitation(receiver=u'lahey@tpb.net',
                                 sender=u'lahey',
                                 code=u'Sunnyvale1',
                                 acceptedTime=90,
                                 target_site='dataserver2')
            self.invitations.add(inv)

        self.testapp.get(site_invitation_url,
                         params={'code': u'Sunnyvale1'},
                         extra_environ=extra_environ,
                         status=303)
