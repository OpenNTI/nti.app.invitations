#!/usr/bin/env python
# -*- coding: utf-8 -*
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# pylint: disable=inherit-non-class

import functools

from zope import interface

from zope.component.zcml import utility

from zope.schema import TextLine


from nti.app.invitations.interfaces import IInvitationSigner

from nti.app.invitations.utils import InvitationSigner

logger = __import__('logging').getLogger(__name__)


class IRegisterInvitationSigner(interface.Interface):
    """
    The arguments needed for registering the invitation signer.
    """
    secret = TextLine(title=u"Shared secret", required=False)
    salt = TextLine(title=u"Namespace used when creating the hash", required=False)


def registerInvitationSigner(_context, secret=None, salt=None):
    """
    Register the signer.
    """
    factory = functools.partial(InvitationSigner,
                                secret=secret,
                                salt=salt)
    utility(_context, provides=IInvitationSigner, factory=factory)
