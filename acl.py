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

from zope.intid.interfaces import IIntIds

from nti.common.property import Lazy

from nti.dataserver.authorization import ACT_READ
from nti.dataserver.authorization import ACT_UPDATE
from nti.dataserver.authorization import ROLE_ADMIN

from nti.dataserver.authorization_acl import ace_allowing
from nti.dataserver.authorization_acl import acl_from_aces

from nti.dataserver.interfaces import ALL_PERMISSIONS

from nti.dataserver.interfaces import IUser
from nti.dataserver.interfaces import IACLProvider

from nti.dataserver.users import get_entity_catalog

from nti.dataserver.users.index import IX_EMAIL

from nti.invitations.interfaces import IInvitation

@component.adapter(IInvitation)
@interface.implementer(IACLProvider)
class InvitationACLProvider(object):

	def __init__(self, context):
		self.context = context

	@property
	def __parent__(self):
		return self.context.__parent__

	@Lazy
	def __acl__(self):
		aces = [ace_allowing(ROLE_ADMIN, ALL_PERMISSIONS, type(self))]
		aces.append(ace_allowing(self.context.sender, ALL_PERMISSIONS, type(self)))

		receiver = self.context.receiver
		if self.context.is_email():
			catalog = get_entity_catalog()
			doc_ids = list(catalog[IX_EMAIL].apply({'any_of': (receiver,)}) or ())
			if len(doc_ids) != 1:
				receiver = None
			else:
				intids = component.getUtility(IIntIds)
				user = IUser(intids.queryObject(doc_ids[0]), None)
				receiver = getattr(user, 'username', None)

		if receiver:
			aces.append(ace_allowing(receiver, ACT_READ, type(self)))
			aces.append(ace_allowing(receiver, ACT_UPDATE, type(self)))

		result = acl_from_aces(aces)
		return result
