#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import component
from zope import interface

from zope.cachedescriptors.property import Lazy

from zope.location.interfaces import ILocation
from zope.location.interfaces import IContained

from nti.dataserver.authentication import  get_current_request

from nti.app.invitations import INVITATIONS
from nti.app.invitations import REL_GENERIC_SITE_INVITATION
from nti.app.invitations import REL_DELETE_SITE_INVITATIONS
from nti.app.invitations import REL_SEND_SITE_INVITATION
from nti.app.invitations import REL_PENDING_SITE_INVITATIONS
from nti.app.invitations import REL_ACCEPT_INVITATION
from nti.app.invitations import REL_DECLINE_INVITATION
from nti.app.invitations import REL_ACCEPT_INVITATIONS
from nti.app.invitations import REL_PENDING_INVITATIONS
from nti.app.invitations import REL_INVITATION_INFO

from nti.app.invitations.interfaces import IInvitationsWorkspace
from nti.app.invitations.interfaces import IUserInvitationsLinkProvider

from nti.app.invitations.views import InvitationsPathAdapter

from nti.appserver.workspaces import IGlobalWorkspaceLinkProvider

from nti.appserver.workspaces.interfaces import IUserService
from nti.appserver.workspaces.interfaces import IUserWorkspace
from nti.appserver.workspaces.interfaces import IContainerCollection

from nti.dataserver.authorization import is_admin_or_site_admin

from nti.dataserver.interfaces import IDataserver
from nti.dataserver.interfaces import IDataserverFolder
from nti.dataserver.interfaces import IUser

from nti.dataserver.users.interfaces import IUserProfile

from nti.invitations.utils import has_pending_invitations

from nti.links.links import Link

from nti.property.property import alias

logger = __import__('logging').getLogger(__name__)


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
        # pylint: disable=not-an-iterable
        for i in self.collections:
            if i.__name__ == key:
                return i
        raise KeyError(key)  # pragma: no cover

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

    @Lazy
    def _dataserver(self):
        request = get_current_request()
        return request.virtual_root

    @property
    def _user(self):
        return self.__parent__.user

    @property
    def links(self):
        result = []
        for provider in list(component.subscribers((self._user,),
                                                   IUserInvitationsLinkProvider) +
                             component.subscribers((self._dataserver, self._user),
                                                   IUserInvitationsLinkProvider)):
            links = provider.links(self.__parent__)
            result.extend(links or ())
        return result

    @property
    def container(self):  # pragma: no cover
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
            link.__name__ = REL_PENDING_INVITATIONS
            link.__parent__ = self.user
            interface.alsoProvides(link, ILocation)
            result.append(link)
        return result


@component.adapter(IDataserverFolder, IUser)
@interface.implementer(IUserInvitationsLinkProvider)
class _DefaultSiteInvitationsLinksProvider(object):

    def __init__(self, ds=None, user=None):
        self.ds = ds
        self.user = user

    def _create_link(self, name, rel, method, parent):
        link = Link(self.ds,
                    method=method,
                    rel=rel,
                    elements=(INVITATIONS, '@@' + name))
        link.__name__ = name
        link.__parent__ = parent
        interface.alsoProvides(link, ILocation)
        return link

    def links(self, unused_workspace):
        result = []

        # TODO we may not want this quite so rigid
        if not is_admin_or_site_admin(self.user):
            return result
        
        link = Link(self.ds,
                    method='GET',
                    rel=INVITATIONS,
                    elements=(INVITATIONS,))
        link.__name__ = INVITATIONS
        link.__parent__ = InvitationsPathAdapter
        interface.alsoProvides(link, ILocation)
        result.append(link)

        for name in (REL_SEND_SITE_INVITATION,
                     REL_DELETE_SITE_INVITATIONS):
            link = self._create_link(name, name, 'POST', InvitationsPathAdapter)
            result.append(link)

        for name in (REL_PENDING_SITE_INVITATIONS,):
            link = self._create_link(name, name, 'GET', InvitationsPathAdapter)
            result.append(link)

        for (method, rel) in (('POST', 'set'),
                              ('PUT', 'update'),
                              ('DELETE', 'delete'),
                              ('GET', 'get')):
            generic_link = self._create_link(REL_GENERIC_SITE_INVITATION,
                                             rel + '-generic-site-invitation',
                                             method,
                                             InvitationsPathAdapter)
            result.append(generic_link)

        return result


@interface.implementer(IGlobalWorkspaceLinkProvider)
class _GlobalWorkspaceLinkProvider(object):

    def __init__(self, unused_user):
        pass

    def links(self, unused_workspace):
        ds2 = component.getUtility(IDataserver).dataserver_folder
        link = Link(ds2, rel=REL_INVITATION_INFO, method='GET',
                    elements=(REL_INVITATION_INFO,))
        return [link]
