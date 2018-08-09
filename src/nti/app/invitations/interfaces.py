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

from nti.app.invitations import MessageFactory as _

from nti.appserver.workspaces.interfaces import IWorkspace

from nti.invitations.interfaces import IInvitation, InvitationValidationError
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


class ISiteInvitation(interface.Interface):
    """
    Interface for an invitation to join a site
    """

    target_site = ValidTextLine(title=u'The target site name',
                                required=True)


class IGenericSiteInvitation(interface.Interface):
    """
    Singleton site invitation interface for generic site invitations
    """


class ISiteInvitationActor(IInvitationActor):
    """
    Actor to add a user to a site
    """


class IChallengeLogonProvider(interface.Interface):
    """
    A utility for defining where accepted site invitations
    should be redirected. This can be be implemented on
    a site-by-site basis for special login cases (OAUTH, etc)
    """

    def logon_url(request):
        """
        :return: The logon destination for the site this is configured in
        """


class InvitationRequiredError(InvitationValidationError):
    __doc__ = _(u'An invitation is required for account creation on this site.')
    i18n_message = __doc__
