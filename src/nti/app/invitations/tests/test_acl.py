#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# pylint: disable=protected-access,too-many-public-methods,arguments-differ

from hamcrest import none
from hamcrest import is_not
from hamcrest import has_length
from hamcrest import assert_that
from hamcrest import greater_than
from hamcrest import has_property
does_not = is_not

from zope import component

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.dataserver.interfaces import IACLProvider

from nti.dataserver.tests import mock_dataserver

from nti.invitations.interfaces import IInvitationsContainer

from nti.invitations.model import Invitation


class TestACL(ApplicationLayerTest):

    @mock_dataserver.WithMockDSTrans
    def test_acl(self):
        self._create_user(username=u'ichigo',
                          external_value={'email': u"ichigo@bleach.org",
                                          'realname': u'ichigo kurosaki',
                                          'alias': u'ichigo'})
        invitations = component.getUtility(IInvitationsContainer)
        invitation = Invitation(receiver=u"ichigo@bleach.org",
                                sender=u'aizen')
        invitations.add(invitation)
        provider = IACLProvider(invitation, None)
        assert_that(provider, is_not(none()))
        assert_that(provider,
                    has_property('__acl__', has_length(greater_than(1))))
