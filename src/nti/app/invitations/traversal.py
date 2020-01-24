#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import interface

from nti.app.invitations import REL_INVITATION_INFO
from nti.app.invitations import SITE_INVITATION_SESSION_KEY
from nti.appserver.account_creation_views import AccountCreatePathAdapter
from nti.appserver.account_creation_views import AccountCreatePreflightPathAdapter
from nti.dataserver.authentication import get_current_request
from nti.dataserver.authorization import ACT_READ
from nti.dataserver.authorization_acl import ace_allowing
from nti.dataserver.authorization_acl import ace_allowing_all
from nti.dataserver.authorization_acl import ace_denying_all
from nti.dataserver.authorization_acl import acl_from_aces
from nti.dataserver.interfaces import EVERYONE_USER_NAME
from zope.container.contained import Contained
from zope.location.interfaces import IContained
from zope.traversing.interfaces import IPathAdapter


class InviteOnlyPathAdapterMixin(object):

    def _has_invitation(self):
        request = get_current_request()

        invitation_code = request.session.get(SITE_INVITATION_SESSION_KEY)

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


@interface.implementer(IPathAdapter, IContained)
class InvitationInfoPathAdapter(InviteOnlyPathAdapterMixin, Contained):
    """
    This object or a subclass must be registered as a path adapter
    named :const:`REL_INVITATION_INFO`.

    This object provides ACL access to users to retrieve info on
    invitations they are in the process of accepting.
    """

    __name__ = REL_INVITATION_INFO

    def __init__(self, context, unused_request):
        self.__parent__ = context

    @property
    def __acl__(self):
        return acl_from_aces(ace_allowing(EVERYONE_USER_NAME, ACT_READ, type(self))) \
            if self._has_invitation() else acl_from_aces(ace_denying_all(self))


