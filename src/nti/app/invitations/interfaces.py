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

from nti.schema.field import DecodingValidTextLine as ValidTextLine


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
