#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component
from zope import interface

from zope.container.contained import Contained

from zope.location.interfaces import ILocation

from nti.app.invitations import REL_ACCEPT_INVITATIONS

from nti.app.invitations.interfaces import IInvitationsWorkspace
from nti.app.invitations.interfaces import IUserInvitationsLinkProvider

from nti.appserver.workspaces.interfaces import IUserService
from nti.appserver.workspaces.interfaces import IUserWorkspace
from nti.appserver.workspaces.interfaces import IContainerCollection

from nti.common.property import Lazy
from nti.common.property import alias

from nti.dataserver.interfaces import IUser

from nti.links.links import Link

@interface.implementer(IInvitationsWorkspace)
class _InvitationsWorkspace(Contained):

	__name__ = 'Invitations'
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

	name = 'Invitations'

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
		for provider in component.subscribers((self._user,), IUserInvitationsLinkProvider):
			links = provider.links(self.__parent__)
			result.extend(links or ())
		return tuple(result)

	@property
	def container(self):
		return ()

	@property
	def accepts(self):
		return ()

@component.adapter(IUser)
@interface.implementer(IUserInvitationsLinkProvider)
class _DefaultUserInvitationsLinkProvider(object):
		
	def __init__(self, user=None):
		self.user = user

	def links(self, workspace):
		link = Link(self.user, 
					method="POST",
					rel=REL_ACCEPT_INVITATIONS, 
					elements=('@@' + REL_ACCEPT_INVITATIONS,))
		link.__name__ = REL_ACCEPT_INVITATIONS
		link.__parent__ = self.user
		interface.alsoProvides(link, ILocation)
		return (link,)
