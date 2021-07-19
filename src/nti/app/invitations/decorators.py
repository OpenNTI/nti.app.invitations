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

from nti.app.invitations import INVITATIONS
from nti.app.invitations import REL_ACCEPT_INVITATIONS
from nti.app.invitations import REL_TRIVIAL_DEFAULT_INVITATION_CODE

from nti.app.invitations.utils import get_invitation_url

from nti.app.invitations.interfaces import ISiteInvitation

from nti.app.renderers.decorators import AbstractTwoStateViewLinkDecorator
from nti.app.renderers.decorators import AbstractAuthenticatedRequestAwareDecorator

from nti.appserver.pyramid_authorization import is_writable

from nti.dataserver.authorization import is_admin_or_site_admin

from nti.dataserver.interfaces import IUser 
from nti.dataserver.interfaces import IDataserverFolder
from nti.dataserver.interfaces import IDynamicSharingTargetFriendsList

from nti.externalization.interfaces import StandardExternalFields
from nti.externalization.interfaces import IExternalMappingDecorator

from nti.links.links import Link

from nti.traversal.traversal import find_interface

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
class SiteInvitationLinkProvider(AbstractAuthenticatedRequestAwareDecorator):

    def add_admin_links(self, context, result, app_url=None):
        _links = result.setdefault(LINKS, [])

        redemption_link = get_invitation_url(app_url, context)
        _links.append(
            Link(redemption_link, rel='redeem')
        )
        ds2 = find_interface(context, IDataserverFolder, strict=False)
        if ds2 is not None:
            _links.append(
                Link(ds2, rel='delete', elements=(INVITATIONS, context.code))
            )

    def _do_decorate_external(self, context, result):
        if is_admin_or_site_admin(self.remoteUser):
            self.add_admin_links(context, result)
