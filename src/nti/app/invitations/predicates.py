#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import component

from nti.dataserver.interfaces import IUser
from nti.dataserver.interfaces import ISystemUserPrincipal

from nti.dataserver.metadata.predicates import BasePrincipalObjects

from nti.invitations.interfaces import IInvitationsContainer

logger = __import__('logging').getLogger(__name__)


@component.adapter(ISystemUserPrincipal)
class SystemInvitationsObjects(BasePrincipalObjects):

    @property
    def invitations(self):
        return component.getUtility(IInvitationsContainer)

    def iter_objects(self):
        for obj in self.invitations.values():
            if self.is_system_username(self.creator(obj)):
                yield obj


@component.adapter(IUser)
class UserInvitationsObjects(BasePrincipalObjects):

    @property
    def invitations(self):
        return component.getUtility(IInvitationsContainer)

    def iter_objects(self):
        for obj in self.invitations.values():
            if self.creator(obj) == self.username:
                yield obj
