#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import interface

from nti.app.invitations.interfaces import IJoinEntityInvitation
from nti.app.invitations.interfaces import IJoinEntityInvitationActor
from nti.app.invitations.interfaces import IJoinEntityAndGrantPermissionInvitation

from nti.dataserver.interfaces import ICommunity
from nti.dataserver.interfaces import IFriendsList

from nti.dataserver.users.entity import Entity

from nti.invitations.model import Invitation

from nti.schema.fieldproperty import createDirectFieldProperties

logger = __import__('logging').getLogger(__name__)


@interface.implementer(IJoinEntityInvitation)
class JoinEntityInvitation(Invitation):
    createDirectFieldProperties(IJoinEntityInvitation)

    mimeType = mime_type = "application/vnd.nextthought.joinentityinvitation"
JoinCommunityInvitation = JoinEntityInvitation

@interface.implementer(IJoinEntityInvitation)
class JoinEntityAndGrantPermissionInvitation(JoinEntityInvitation):
    createDirectFieldProperties(IJoinEntityAndGrantPermissionInvitation)

    # TODO: That's a long mimetype...
    mimeType = mime_type = "application/vnd.nextthought.joinentityandgrantpermissioninvitation"
JoinSiteInvitation = JoinEntityAndGrantPermissionInvitation


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


@interface.implementer(IJoinEntityInvitationActor)
class JoinEntityAndGrantPermissionActor(object):
    pass