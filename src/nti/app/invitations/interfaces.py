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

from nti.invitations.interfaces import IInvitation
from nti.invitations.interfaces import IUserInvitation
from nti.invitations.interfaces import IInvitationActor
from nti.invitations.interfaces import InvitationValidationError

from nti.schema.field import DecodingValidTextLine as ValidTextLine
from nti.schema.field import Bool


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


class ISiteInvitation(IUserInvitation):
    """
    Interface for an invitation to join a site
    """

    target_site = ValidTextLine(title=u'The target site name',
                                required=True)

    receiver_name = ValidTextLine(title=u'The realname of the receiver for this invitation',
                                  required=True)

    target_receiver = ValidTextLine(title=u'The original intended recipient. Not updated '
                                          u'when invitation is accepted.',
                                    required=False)

    require_matching_email = Bool(title=u'Require the email provided during account '
                                        u'creation to match the invitation email.',
                                  required=True,
                                  default=False)

class IGenericSiteInvitation(ISiteInvitation):
    """
    Singleton site invitation interface for generic site invitations
    """


class ISiteAdminInvitation(ISiteInvitation):
    """
    Interface for a site invitation that grants the user site admin privileges
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


class IInvitationSigner(interface.Interface):
    """
    Allow secure delivery of information that can be decoded and verified
    later, e.g. when providing an invitation url with a
    """

    def encode(content):
        """
        Encode and sign content for later verification and decoding.
        :return: 
        """

    def decode(encoded_content):
        """
        Decode the signed content.  Throws exception if signature doesn't match.
        :return:
        """
