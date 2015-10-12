#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Views relating to working with invitations.

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component
from zope import interface

from zope.intid import IIntIds

from pyramid import httpexceptions as hexc

from pyramid.view import view_config
from pyramid.interfaces import IRequest

from nti.app.renderers.decorators import AbstractTwoStateViewLinkDecorator

from nti.appserver.pyramid_authorization import is_writable

from nti.invitations.utility import ZcmlInvitations
from nti.invitations.utility import accept_invitations

from nti.invitations.invitation import JoinEntitiesInvitation

from nti.invitations.interfaces import IInvitations
from nti.invitations.interfaces import InvitationValidationError

from nti.dataserver import authorization as nauth

from nti.dataserver.interfaces import IUser
from nti.dataserver.interfaces import IDynamicSharingTargetFriendsList

from nti.externalization import integer_strings
from nti.externalization.interfaces import IExternalMappingDecorator

from nti.app.externalization import internalization as obj_io
from nti.app.externalization.error import handle_validation_error
from nti.app.externalization.error import handle_possible_validation_error

#: The link relationship type to which an authenticated
#: user can ``POST`` data to accept outstanding invitations. Also the name of a
#: view to handle this feedback: :func:`accept_invitations_view`
#: The data should be an dictionary containing the key ``invitation_codes``
#: whose value is an array of strings naming codes.
#: See also :func:`nti.appserver.account_creation_views.account_create_view`
REL_ACCEPT_INVITATIONS = 'accept-invitations'

#: The link relationship type that will be exposed to the creator of a
#: :class:`nti.dataserver.users.friends_lists.DynamicFriendsList`. A ``GET``
#: to this link will return the invitation code corresponding to the default invitation
#: to join that group, in the form of a dictionary: ``{invitation_code: "thecode"}``
#: If the invitation does not exist, one will be created; at most one such code can exist at a time.
#: There is no way to disable the code at this time (in the future that could be done with a
#: ``DELETE`` to this link type). See also :func:`get_default_trivial_invitation_code`
REL_TRIVIAL_DEFAULT_INVITATION_CODE = 'default-trivial-invitation-code'

@view_config(route_name='objects.generic.traversal',
			 renderer='rest',
			 context=IUser,
			 permission=nauth.ACT_UPDATE,
			 request_method='POST',
			 name=REL_ACCEPT_INVITATIONS)
def accept_invitations_view(request):
	"""
	Implementation of :const:`REL_ACCEPT_INVITATIONS`.
	"""

	json_body = obj_io.read_body_as_external_object(request)
	if 'invitation_codes' not in json_body:
		raise hexc.HTTPBadRequest()

	try:
		invite_codes = json_body['invitation_codes']
		if invite_codes:
			accept_invitations(request.context, invite_codes)
	except InvitationValidationError as e:
		e.field = 'invitation_codes'
		handle_validation_error(request, e)
	except Exception as e:  # pragma: no cover
		handle_possible_validation_error(request, e)

	return hexc.HTTPNoContent()

#: To work better with the ZcmlInvitations, and until we need
#: configured persistent invitations (e.g., user-editable)
#: we synthesize the default invitation. It's tied directly to the
#: intid of the actual object we will be joining. Note that as soon
#: as we go persistent, these codes will probably be invalidated.
#: We only generate invitations to IDynamicSharingTargetFriendsList objects, even
#: though in theory this could work for Communities and regular FL too; this is
#: alright because the accept view and the link provider are also tied to the
#: IDynamicSharingTargetFriendsList

class _DefaultJoinEntityInvitation(JoinEntitiesInvitation):

	def _iter_entities(self):
		yield self.entities

class _TrivialDefaultInvitations(ZcmlInvitations):

	def _getDefaultInvitationCode(self, dfl):
		iid = component.getUtility(IIntIds).getId(dfl)
		return integer_strings.to_external_string(iid)

	def _getObjectByCode(self, code):
		iid = integer_strings.from_external_string(code)
		result = component.getUtility(IIntIds).getObject(iid)
		return result

	def getInvitationByCode(self, code):
		__traceback_info__ = code,
		invite = super(_TrivialDefaultInvitations, self).getInvitationByCode(code)
		if invite is None:
			try:
				dfl = self._getObjectByCode(code)
				if IDynamicSharingTargetFriendsList.providedBy(dfl):
					invite = _DefaultJoinEntityInvitation(code, dfl)
					invite.creator = dfl.creator
			except (KeyError, ValueError, AttributeError):
				return None
		return invite

@view_config(route_name='objects.generic.traversal',
			 renderer='rest',
			 context=IDynamicSharingTargetFriendsList,
			 permission=nauth.ACT_UPDATE, # The creator only, not members who have read access
			 request_method='GET',
			 name=REL_TRIVIAL_DEFAULT_INVITATION_CODE)
def get_default_trivial_invitation_code(request):
	invitations = component.getUtility(IInvitations)
	code = invitations._getDefaultInvitationCode(request.context)
	return {'invitation_code': code}

@interface.implementer(IExternalMappingDecorator)
@component.adapter(IDynamicSharingTargetFriendsList, IRequest)
class DFLGetInvitationLinkProvider(AbstractTwoStateViewLinkDecorator):

	true_view = REL_TRIVIAL_DEFAULT_INVITATION_CODE

	def link_predicate(self, context, username):
		return is_writable(context, self.request) and not context.Locked
