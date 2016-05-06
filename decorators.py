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

from pyramid.interfaces import IRequest

from nti.app.invitations import REL_TRIVIAL_DEFAULT_INVITATION_CODE

from nti.app.renderers.decorators import AbstractTwoStateViewLinkDecorator

from nti.appserver.pyramid_authorization import is_writable

from nti.dataserver.interfaces import IDynamicSharingTargetFriendsList

from nti.externalization.interfaces import IExternalMappingDecorator

@interface.implementer(IExternalMappingDecorator)
@component.adapter(IDynamicSharingTargetFriendsList, IRequest)
class DFLGetInvitationLinkProvider(AbstractTwoStateViewLinkDecorator):

	true_view = REL_TRIVIAL_DEFAULT_INVITATION_CODE

	def link_predicate(self, context, username):
		return is_writable(context, self.request) and not context.Locked
