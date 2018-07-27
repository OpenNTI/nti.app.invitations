#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from nti.coremetadata.interfaces import IDataserver
from nti.dataserver.users import User
from nti.ntiids.ntiids import find_object_with_ntiid
from zope import interface, component

from zope.cachedescriptors.property import readproperty

from nti.app.invitations.interfaces import IAcceptSiteInvitation
from nti.app.invitations.interfaces import IJoinEntityInvitation
from nti.app.invitations.interfaces import IJoinEntityInvitationActor
from nti.app.invitations.interfaces import ISiteInvitation
from nti.app.invitations.interfaces import ISiteInvitationActor

from nti.dataserver.interfaces import ICommunity
from nti.dataserver.interfaces import IFriendsList

from nti.dataserver.users.entity import Entity

from nti.invitations.model import Invitation

from nti.property.property import alias

from nti.schema.fieldproperty import createDirectFieldProperties

logger = __import__('logging').getLogger(__name__)


@interface.implementer(IJoinEntityInvitation)
class JoinEntityInvitation(Invitation):
    createDirectFieldProperties(IJoinEntityInvitation)

    mimeType = mime_type = "application/vnd.nextthought.joinentityinvitation"
JoinCommunityInvitation = JoinEntityInvitation


@interface.implementer(ISiteInvitation)
class JoinSiteInvitation(JoinEntityInvitation):
    createDirectFieldProperties(ISiteInvitation)

    mimeType = mime_type = "application/vnd.nextthought.siteinvitation"

    receiver_email = alias('receiver')
    entity = alias('site')

    @readproperty
    def receiver_name(self):
        return getattr(self.receiver, 'realname', None)


@interface.implementer(IJoinEntityInvitationActor)
class JoinEntityInvitationActor(object):

    def __init__(self, invitation=None):
        self.invitation = invitation

    def accept(self, user, invitation=None):
        result = True
        invitation = self.invitation if invitation is None else invitation
        entity = Entity.get_entity(invitation.entity)
        if entity is None:
            logger.warning("Entity %s does not exists", invitation.entity)
            result = False
        elif ICommunity.providedBy(entity):
            logger.info("Accepting invitation to join community %s", entity)
            user.record_dynamic_membership(entity)
            user.follow(entity)
        elif IFriendsList.providedBy(entity):
            logger.info("Accepting invitation to join DFL %s", entity)
            entity.addFriend(user)
        else:
            result = False
            logger.warning("Don't know how to accept invitation to join entity %s",
                           entity)
        return result


@interface.implementer(ISiteInvitationActor)
class SiteInvitationActor(JoinEntityInvitationActor):

    # context will likely be either IInvitation or IDataserverFolder depending upon if this is a code accept or direct
    def accept(self, context, invitation=None):
        from IPython.terminal.debugger import set_trace;set_trace()

        result = True
        invitation = self.invitation if invitation is None else invitation
        site = find_object_with_ntiid(invitation.site)
        if site is None:
            logger.warning("Site ntiid %s was not found.", invitation.site)
            result = False
        else:
            # This adapter can be implemented on a site to handle adding users in a specific way (OAuth logon, etc)
            accept_invitation = IAcceptSiteInvitation(site)  # TODO check how to do default adapter in this context
            # Check if this invitation was able to be accepted
            result = accept_invitation.do_accept(invitation)
        return result


@interface.implementer(IAcceptSiteInvitation)
class DefaultAcceptSiteInvitation(object):
    # This is a placeholder for future development

    def __init__(self, site):
        self.site = site

    def do_accept(self, invitation):
        if invitation is None:
            return False

        # Accept a site invitation for a regular NT login
        dataserver = component.getUtility(IDataserver)
        user = User.get_user(username=invitation.receiver, dataserver=dataserver)
        # This person already has an NT account
        if user is not None:
            # TODO I don't know what I'm doing
            return False
        # We need to create them an NT account and log them in
        else:
            # TODO Probably even less sure what I'm doing here
            # There could be two cases here
            # 1. The user has been invited to a publicly accessible site
            # in this case we should redirect them to the account creation page.
            # This presents a challenge as to when this invitation should be marked as accepted
            # we will likely need to register a subscriber on an account creation event to
            # determine if this user has followed through. However, the user could create an
            # account with a different email. We may need to put something into the request session
            # to be able to check this more reassuredly
            # 2. The user has been invited to a private site
            # in this case the account creation page isn't accessible
            # so we should create an account for this user with a temporary password
            # and log them in. They should be sent an email containing this information
            # TODO seriously, I'm just making this up
            return False
