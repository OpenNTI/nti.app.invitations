#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from pyramid.interfaces import IRequest

from zope import component
from zope import interface

from zope.location.interfaces import ILocation

from nti.app.invitations import REL_ACCEPT_INVITATIONS
from nti.app.invitations import REL_ACCEPT_SITE_INVITATION
from nti.app.invitations import REL_TRIVIAL_DEFAULT_INVITATION_CODE

from nti.app.invitations.interfaces import ISiteInvitation

from nti.app.renderers.decorators import AbstractTwoStateViewLinkDecorator
from nti.app.renderers.decorators import AbstractAuthenticatedRequestAwareDecorator
from nti.app.renderers.decorators import AbstractRequestAwareDecorator

from nti.appserver.pyramid_authorization import is_writable

from nti.dataserver.interfaces import IUser
from nti.dataserver.interfaces import IDynamicSharingTargetFriendsList

from nti.externalization.interfaces import StandardExternalFields
from nti.externalization.interfaces import IExternalMappingDecorator

from nti.links.links import Link

LINKS = StandardExternalFields.LINKS

logger = __import__('logging').getLogger(__name__)


@interface.implementer(IExternalMappingDecorator)
@component.adapter(IDynamicSharingTargetFriendsList, IRequest)
class DFLGetInvitationLinkProvider(AbstractTwoStateViewLinkDecorator):

    true_view = REL_TRIVIAL_DEFAULT_INVITATION_CODE

    def link_predicate(self, context, unused_username):
        return is_writable(context, self.request) and not context.Locked


@component.adapter(IUser, IRequest)
@interface.implementer(IExternalMappingDecorator)
class LegacyAcceptInvitationsLinkProvider(AbstractAuthenticatedRequestAwareDecorator):

    accept = REL_ACCEPT_INVITATIONS

    def _do_decorate_external(self, context, result):
        _links = result.setdefault(LINKS, [])
        link = Link(context, rel=self.accept, elements=(self.accept,))
        interface.alsoProvides(link, ILocation)
        link.__parent__ = context
        link.__name__ = self.accept
        _links.append(link)


@component.adapter(ISiteInvitation, IRequest)
@interface.implementer(IExternalMappingDecorator)
class SiteInvitationDeleteLinkProvider(AbstractAuthenticatedRequestAwareDecorator):

    def _do_decorate_external(self, context, result):
        _links = result.setdefault(LINKS, [])
        _links.append(
            Link(context, rel='delete', elements=('@@decline',))
        )


@component.adapter(ISiteInvitation, IRequest)
@interface.implementer(IExternalMappingDecorator)
class SiteInvitationAcceptLinkProvider(AbstractRequestAwareDecorator):

    def _do_decorate_external(self, context, result):
        _links = result.setdefault(LINKS, [])
        _links.append(
            Link(context, rel=REL_ACCEPT_SITE_INVITATION, elements=('@@' + REL_ACCEPT_SITE_INVITATION,))
        )
