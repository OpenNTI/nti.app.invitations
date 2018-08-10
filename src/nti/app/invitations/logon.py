#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
from __future__ import absolute_import
from __future__ import division

from zope import interface

from nti.app.invitations.interfaces import IChallengeLogonProvider

from nti.schema.fieldproperty import createDirectFieldProperties

from nti.schema.schema import SchemaConfigured

__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)


@interface.implementer(IChallengeLogonProvider)
class ChallengeLogonProvider(SchemaConfigured):
    createDirectFieldProperties(IChallengeLogonProvider)

    def logon_url(self, request):
        return request.application_url
