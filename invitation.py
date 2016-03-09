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

from nti.dataserver.interfaces import IEntity

from nti.dataserver.users import Entity

from nti.dataserver.interfaces import IDynamicSharingTargetFriendsList

from nti.externalization import integer_strings

from nti.invitations.interfaces import IInvitationEntityFinder

from nti.invitations.invitation import JoinEntitiesInvitation

from nti.invitations.utility import ZcmlInvitations

@interface.implementer(IInvitationEntityFinder)
class InvitationEntityFinder(object):
    
    def find(self, entity):
        if entity is not None and not IEntity.providedBy(entity):
            return Entity.get_entity(str(entity))
        return entity

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
                    invite = _DefaultJoinEntityInvitation(code, (dfl,))
                    invite.creator = dfl.creator
            except (KeyError, ValueError, AttributeError):
                return None
        return invite
