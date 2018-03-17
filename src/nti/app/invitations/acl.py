#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component
from zope import interface

from zope.cachedescriptors.property import Lazy

from zope.security.interfaces import IPrincipal

from nti.dataserver.authorization import ACT_READ
from nti.dataserver.authorization import ACT_UPDATE
from nti.dataserver.authorization import ROLE_ADMIN

from nti.dataserver.authorization_acl import ace_allowing
from nti.dataserver.authorization_acl import acl_from_aces

from nti.dataserver.interfaces import ACE_DENY_ALL
from nti.dataserver.interfaces import ALL_PERMISSIONS

from nti.dataserver.interfaces import IACLProvider

from nti.dataserver.users.users import User

from nti.dataserver.users.utils import get_users_by_email

from nti.invitations.interfaces import IInvitation


@component.adapter(IInvitation)
@interface.implementer(IACLProvider)
class InvitationACLProvider(object):

    def __init__(self, context):
        self.context = context

    @classmethod
    def _get_usernames_by_email(cls, email):
        users = get_users_by_email(email)
        result = {x.username for x in users or ()}
        return tuple(result)

    @Lazy
    def __acl__(self):
        aces = [ace_allowing(ROLE_ADMIN, ALL_PERMISSIONS, type(self))]
        aces.append(ace_allowing(IPrincipal(self.context.sender),
                                 ALL_PERMISSIONS,
                                 type(self)))

        receiver = self.context.receiver.lower()
        if self.context.is_email():
            user = User.get_user(receiver)
            if user is None:
                usernames = self._get_usernames_by_email(receiver)
                receiver = usernames[0] if len(usernames) == 1 else None
        if receiver:
            receiver = IPrincipal(receiver.lower())
            aces.append(ace_allowing(receiver, ACT_READ, type(self)))
            aces.append(ace_allowing(receiver, ACT_UPDATE, type(self)))
        aces.append(ACE_DENY_ALL)
        result = acl_from_aces(aces)
        return result
