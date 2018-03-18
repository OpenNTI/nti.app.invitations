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


class IInvitationsWorkspace(IWorkspace):
    """
    A workspace containing data for invitations.
    """


class IUserInvitationsLinkProvider(interface.Interface):

    def links(workspace):
        """
        return an interable of user invitation links
        """
