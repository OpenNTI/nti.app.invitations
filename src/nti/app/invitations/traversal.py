#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from nti.app.invitations import SITE_INVITATION_SESSION_KEY
from nti.appserver.account_creation_views import AccountCreatePathAdapter
from nti.appserver.account_creation_views import AccountCreatePreflightPathAdapter
from nti.dataserver.authentication import get_current_request
from nti.dataserver.authorization_acl import ace_allowing_all
from nti.dataserver.authorization_acl import ace_denying_all
from nti.dataserver.authorization_acl import acl_from_aces
from nti.invitations.interfaces import IInvitationsContainer
from zope import component


class InviteOnlyPathAdapterMixin(object):

    def _has_invitation(self):
        request = get_current_request()

        # We only have the code in the session, not the object
        invitation_code = request.session.get(SITE_INVITATION_SESSION_KEY)

        invitations = component.getUtility(IInvitationsContainer)
        invitation = invitations.get_invitation_by_code(invitation_code)

        return bool(invitation_code)


class InviteOnlyAccountCreatePathAdapter(InviteOnlyPathAdapterMixin, AccountCreatePathAdapter):
    """
    Restrict account creation to only users with an invitation
    """

    @property
    def __acl__(self):
        return acl_from_aces(ace_allowing_all(self)) \
            if self._has_invitation() else acl_from_aces(ace_denying_all(self))


class InviteOnlyAccountCreatePreflightPathAdapter(InviteOnlyPathAdapterMixin, AccountCreatePreflightPathAdapter):
    """
    Restrict account creation to only users with an invitation
    """

    @property
    def __acl__(self):
        return acl_from_aces(ace_allowing_all(self)) \
            if self._has_invitation() else acl_from_aces(ace_denying_all(self))


