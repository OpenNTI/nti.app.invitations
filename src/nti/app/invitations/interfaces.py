#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# pylint: disable=inherit-non-class,expression-not-assigned

from zope import interface

from nti.appserver.workspaces.interfaces import IWorkspace

from nti.invitations.interfaces import IInvitation
from nti.invitations.interfaces import IInvitationActor

from nti.schema.field import DecodingValidTextLine as ValidTextLine, List


class IInvitationsWorkspace(IWorkspace):
    """
    A workspace containing data for invitations.
    """


class IUserInvitationsLinkProvider(interface.Interface):

    def links(workspace):
        """
        return an interable of user invitation links
        """


class IJoinEntityInvitation(IInvitation):
    """
    Interface for a invitation to join entities
    """

    entity = ValidTextLine(title=u"The entity username", required=True)


class IJoinEntityInvitationActor(IInvitationActor):
    """
    Actor to join a user to an entity
    """


class IJoinEntityAndGrantPermissionInvitation(IJoinEntityInvitation):
    """
    Interface for an invitation to join an entity and grant specific permissions
    """

    entity = ValidTextLine(title=u'The entity name',
                           required=True)

    permissions = List(title=u'The permissions this user will be granted',
                       required=True)
ISiteInvitation = IJoinEntityAndGrantPermission


class IJoinSiteInvitationFactory(interface.Interface):
    """
    Interface for a factory that determines how to add a user to a site
    """

    def handle_invitation(self, user):
        """
        Handle the invitation for this user according to site specifications
        This is used to determine the creation flow for this user e.g. OAuth2, NT, etc
        """