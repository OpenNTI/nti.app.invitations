#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import six

from pyramid.view import view_config
from pyramid.view import view_defaults

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.externalization.internalization import read_body_as_external_object
from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.app.invitations.views import InvitationsPathAdapter

from nti.common.maps import CaseInsensitiveDict

from nti.dataserver import authorization as nauth

from nti.dataserver.interfaces import IDataserverFolder

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields

from nti.invitations.utils import get_expired_invitations
from nti.invitations.utils import delete_expired_invitations

ITEMS = StandardExternalFields.ITEMS
TOTAL = StandardExternalFields.TOTAL
ITEM_COUNT = StandardExternalFields.ITEM_COUNT

@view_config(context=IDataserverFolder)
@view_config(context=InvitationsPathAdapter)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   request_method='GET',
			   permission=nauth.ACT_NTI_ADMIN,
			   name='ExpiredInvitations')
class GetExpiredInvitationsView(AbstractAuthenticatedView):

	def __call__(self):
		values = CaseInsensitiveDict(self.request.params)
		usernames = values.get('username') or values.get('usernames')
		if isinstance(usernames, six.string_types):
			usernames = usernames.split(",")
		usernames = None if not usernames else set(usernames)
		result = LocatedExternalDict()
		items = result[ITEMS] = get_expired_invitations(usernames)
		result[TOTAL] = result[ITEM_COUNT] = len(items)
		result.__name__ = self.request.view_name
		result.__parent__ = self.request.context
		return result

@view_config(context=IDataserverFolder)
@view_config(context=InvitationsPathAdapter)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   permission=nauth.ACT_NTI_ADMIN,
			   name='DeleteExpiredInvitations')
class DeleteExpiredInvitationsView(AbstractAuthenticatedView,
								   ModeledContentUploadRequestUtilsMixin):

	def readInput(self, value=None):
		if self.request.body:
			result = CaseInsensitiveDict(read_body_as_external_object(self.request))
		else:
			result = CaseInsensitiveDict()
		return result

	def __call__(self):
		values = self.readInput()
		usernames = values.get('username') or values.get('usernames')
		if isinstance(usernames, six.string_types):
			usernames = usernames.split(",")
		usernames = None if not usernames else set(usernames)
		result = LocatedExternalDict()
		items = result[ITEMS] = delete_expired_invitations(usernames)
		result[TOTAL] = result[ITEM_COUNT] = len(items)
		result.__name__ = self.request.view_name
		result.__parent__ = self.request.context
		return result
