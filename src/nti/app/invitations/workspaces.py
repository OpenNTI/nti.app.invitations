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

from zope.location.interfaces import ILocation
from zope.location.interfaces import IContained

from nti.app.invitations import INVITATIONS
from nti.app.invitations import REL_ACCEPT_INVITATION
from nti.app.invitations import REL_DECLINE_INVITATION
from nti.app.invitations import REL_ACCEPT_INVITATIONS
from nti.app.invitations import REL_PENDING_INVITATIONS

from nti.app.invitations.interfaces import IInvitationsWorkspace
from nti.app.invitations.interfaces import IUserInvitationsLinkProvider

from nti.appserver.workspaces.interfaces import IUserService
from nti.appserver.workspaces.interfaces import IUserWorkspace
from nti.appserver.workspaces.interfaces import IContainerCollection

from nti.dataserver.interfaces import IUser

from nti.dataserver.users.interfaces import IUserProfile

from nti.invitations.utils import has_pending_invitations

from nti.links.links import Link

from nti.property.property import alias


@interface.implementer(IInvitationsWorkspace, IContained)
class _InvitationsWorkspace(object):

    __parent__ = None
    __name__ = INVITATIONS

    name = alias('__name__', __name__)

    links = ()

    def __init__(self, user_service):
        self.context = user_service
        self.user = user_service.user

    def __getitem__(self, key):
        """
        Make us traversable to collections.
        """
        for i in self.collections:
            if i.__name__ == key:
                return i
        raise KeyError(key)

    def __len__(self):
        return len(self.collections)

    @Lazy
    def collections(self):
        return (_InvitationsCollection(self),)


@component.adapter(IUserService)
@interface.implementer(IInvitationsWorkspace)
def InvitationsWorkspace(user_service):
    workspace = _InvitationsWorkspace(user_service)
    workspace.__parent__ = workspace.user
    return workspace


@component.adapter(IUserWorkspace)
@interface.implementer(IContainerCollection)
class _InvitationsCollection(object):

    name = INVITATIONS

    __name__ = u''
    __parent__ = None

    def __init__(self, user_workspace):
        self.__parent__ = user_workspace

    @property
    def _user(self):
        return self.__parent__.user

    @property
    def links(self):
        result = []
        for provider in list(component.subscribers((self._user,),
                                                   IUserInvitationsLinkProvider)):
            links = provider.links(self.__parent__)
            result.extend(links or ())
        return result

    @property
    def container(self):
        return ()

    @property
    def accepts(self):
        return ()


@component.adapter(IUser)
@interface.implementer(IUserInvitationsLinkProvider)
class _DefaultUserInvitationsLinksProvider(object):

    def __init__(self, user=None):
        self.user = user

    def links(self, unused_workspace):
        result = []
        for name in (REL_ACCEPT_INVITATIONS,
                     REL_ACCEPT_INVITATION,
                     REL_DECLINE_INVITATION):
            link = Link(self.user,
                        method="POST",
                        rel=name,
                        elements=('@@' + name,))
            link.__name__ = name
            link.__parent__ = self.user
            interface.alsoProvides(link, ILocation)
            result.append(link)

        username = self.user.username
        email = getattr(IUserProfile(self.user, None), 'email', None)
        if has_pending_invitations(receivers=(username, email)):
            link = Link(self.user,
                        method="GET",
                        rel=REL_PENDING_INVITATIONS,
                        elements=('@@' + REL_PENDING_INVITATIONS,))
            link.__name__ = name
            link.__parent__ = self.user
            interface.alsoProvides(link, ILocation)
            result.append(link)
        return result
