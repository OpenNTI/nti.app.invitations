#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# pylint: disable=protected-access,too-many-public-methods,arguments-differ

from hamcrest import is_
from hamcrest import assert_that

from nti.app.invitations.invitations import JoinEntityInvitation
from nti.app.invitations.invitations import JoinEntityInvitationActor

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.dataserver.tests import mock_dataserver


class TesInvitations(ApplicationLayerTest):

    @WithSharedApplicationMockDS
    def test_validation(self):

        with mock_dataserver.mock_db_trans(self.ds):
            user = self._create_user()
            actor = JoinEntityInvitationActor()
            # missing entity
            invitation = JoinEntityInvitation()
            invitation.entity = 'invalid'
            invitation.receiver = self.default_username
            assert_that(actor.accept(user, invitation),
                        is_(False))
            # invalid entity
            invitation.entity = self.default_username
            invitation.receiver = self.default_username
            assert_that(actor.accept(user, invitation),
                        is_(False))
