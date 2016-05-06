#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Views relating to working with invitations.

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from pyramid.view import view_config
from pyramid.view import view_defaults

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.invitations import REL_EXPIRED_INVITATIONS

from nti.dataserver import authorization as nauth

from nti.dataserver.interfaces import IDataserverFolder

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields

from nti.invitations.utils import get_expired_invitations

ITEMS = StandardExternalFields.ITEMS

@view_config(context=IDataserverFolder)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   permission=nauth.ACT_READ,
			   request_method='GET',
			   name=REL_EXPIRED_INVITATIONS)
class GetExpiredInvitationsView(AbstractAuthenticatedView):

	def __call__(self):
		"""
		Implementation of :const:`REL_EXPIRED_INVITATIONS`.
		"""
		result = LocatedExternalDict()
		result[ITEMS] = get_expired_invitations()
		result.__name__ = self.request.view_name
		result.__parent__ = self.request.context
		return result
