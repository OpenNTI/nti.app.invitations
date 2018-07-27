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

from nti.schema.field import Bool
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


class ISiteInvitation(IJoinEntityInvitation):
    """
    Interface for an invitation to join a site
    """

    entity = ValidTextLine(title=u'The site NTIID',
                           required=True)

    IsGeneric = Bool(title=u'The invitation code is generic',
                     required=False,
                     default=False)
    IsGeneric.setTaggedValue('_ext_excluded_out', True)


class ISiteInvitationActor(IInvitationActor):
    """
    Actor to add a user to a site
    """


class IAcceptSiteInvitation(interface.Interface):
    """
    Handles accepting a site invitation
    """

    def do_accept(invitation):
        """
        This method can be implemented in specific sites to handle atypical site login flows such as OAuth, etc
        """
