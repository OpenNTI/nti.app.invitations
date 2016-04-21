#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Views relating to working with invitations.

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import six

from zope import component
from zope import interface

from pyramid import httpexceptions as hexc

from pyramid.interfaces import IRequest

from pyramid.view import view_config

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.externalization import internalization as obj_io

from nti.app.externalization.error import handle_validation_error
from nti.app.externalization.error import handle_possible_validation_error

from nti.app.invitations import REL_ACCEPT_INVITATIONS
from nti.app.invitations import REL_TRIVIAL_DEFAULT_INVITATION_CODE

from nti.app.renderers.decorators import AbstractTwoStateViewLinkDecorator

from nti.appserver.pyramid_authorization import is_writable

from nti.dataserver import authorization as nauth

from nti.dataserver.interfaces import IUser
from nti.dataserver.interfaces import IDynamicSharingTargetFriendsList

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import IExternalMappingDecorator

from nti.invitations.interfaces import IInvitations
from nti.invitations.interfaces import InvitationValidationError

from nti.invitations.utility import accept_invitations

@view_config(route_name='objects.generic.traversal',
			 renderer='rest',
			 context=IUser,
			 permission=nauth.ACT_UPDATE,
			 request_method='POST',
			 name=REL_ACCEPT_INVITATIONS)
class AcceptInvitationsView(AbstractAuthenticatedView):

	def get_invite_codes(self):
		json_body = obj_io.read_body_as_external_object(self.request)
		if 'invitation_codes' not in json_body:
			raise hexc.HTTPBadRequest()
		result = json_body['invitation_codes']
		if isinstance(result, six.string_types):
			result = result.split()
		return result

	def handle_validation_error(self, request, e):
		handle_validation_error(request, e)

	def handle_possible_validation_error(self, request, e):
		handle_possible_validation_error(request, e)
		
	def _do_call(self):
		request = self.request
		invite_codes = self.get_invite_codes()	
		try:
			if invite_codes:
				return accept_invitations(request.context, invite_codes)
		except InvitationValidationError as e:
			e.field = 'invitation_codes'
			self.handle_validation_error(request, e)
		except Exception as e:  # pragma: no cover
			self.handle_possible_validation_error(request, e)

	def __call__(self):
		"""
		Implementation of :const:`REL_ACCEPT_INVITATIONS`.
		"""
		self._do_call()
		return hexc.HTTPNoContent()

@view_config(route_name='objects.generic.traversal',
			 renderer='rest',
			 context=IDynamicSharingTargetFriendsList,
			 permission=nauth.ACT_UPDATE, # The creator only, not members who have read access
			 request_method='GET',
			 name=REL_TRIVIAL_DEFAULT_INVITATION_CODE)
def get_default_trivial_invitation_code(request):
	invitations = component.getUtility(IInvitations)
	code = invitations._getDefaultInvitationCode(request.context)
	return LocatedExternalDict({'invitation_code': code})

@interface.implementer(IExternalMappingDecorator)
@component.adapter(IDynamicSharingTargetFriendsList, IRequest)
class DFLGetInvitationLinkProvider(AbstractTwoStateViewLinkDecorator):

	true_view = REL_TRIVIAL_DEFAULT_INVITATION_CODE

	def link_predicate(self, context, username):
		return is_writable(context, self.request) and not context.Locked
