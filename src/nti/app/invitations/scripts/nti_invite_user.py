#!/usr/bin/env python
# -*- coding: utf-8 -*
"""
Creates an entity

.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import json

from nti.app.invitations.decorators import SiteInvitationLinkProvider
from nti.externalization import to_external_object
from nti.monkey import patch_relstorage_all_except_gevent_on_import

patch_relstorage_all_except_gevent_on_import.patch()

import argparse
import calendar
import datetime
import os
import re
import sys

from zope import component
from zope.component.hooks import getSite

from nti.app.invitations.invitations import SiteAdminInvitation
from nti.app.invitations.invitations import SiteInvitation

from nti.app.invitations.utils import get_invitation_url

from nti.dataserver.users.interfaces import checkEmailAddress

from nti.dataserver.utils import run_with_dataserver

from nti.dataserver.utils.base_script import set_site
from nti.dataserver.utils.base_script import create_context

from nti.invitations.interfaces import IInvitationsContainer

from nti.invitations.utils import get_random_invitation_code

logger = __import__('logging').getLogger(__name__)

regex = re.compile(r'((?P<days>\d+?)d)?((?P<hours>\d+?)h)?((?P<minutes>\d+?)m)?((?P<seconds>\d+?)s)?$')


def parse_time(time_str):
    parts = regex.match(time_str)

    if not parts:
        print("Improper format for \"expiry\".  Must be integer followed by "
              "time specifier of \"d\", \"h\", \"m\", or \"s\"")
        exit(2)

    parts = parts.groupdict()
    time_params = {}

    if not parts:
        print("time_params = %s" % parts)
        print("Improper format for \"expiry\".  Must be integer followed by "
              "time specifier of \"d\", \"h\", \"m\", or \"s\"")
        exit(2)

    for (name, param) in parts.iteritems():
        if param:
            time_params[name] = int(param)
    return datetime.timedelta(**time_params)


def _preflight_email(email):
    if not checkEmailAddress(email):
        print("Must provide valid email.")
        sys.exit(2)

    return email


def _create_site_invitation(email, realname, site_name, is_admin, expiry, as_json=False):
    """
    Used to create an invitation and return a URL that can be given to a
    user to redeem the invitation.  Takes an email, realname and site, and
    optionally whether the invitation should be for a site admin (defaults
    to false).  Should only be accessible to admin users.
    """

    set_site(site_name)

    validated_email = _preflight_email(email.strip() if email else email)

    invitation = create_invitation(validated_email, realname, is_admin, expiry)

    invitations = component.getUtility(IInvitationsContainer)
    invitations.add(invitation)

    if as_json:
        decorator = SiteInvitationLinkProvider(None, None)
        ext = to_external_object(invitation)
        decorator.add_admin_links(invitation, ext)

        # Once more, with feeling (links need externalized)
        print(json.dumps(to_external_object(ext)))
    else:
        print(get_invitation_url(None, invitation))


def create_invitation(email, realname, is_admin, expiry):
    factory = SiteAdminInvitation if is_admin else SiteInvitation

    invitation = factory()
    invitation.code = get_random_invitation_code()
    invitation.target_site = getSite().__name__
    invitation.receiver = email
    invitation.receiver_name = realname

    if expiry:
        expire_date = expiry_date(expiry)
        logger.info("Using expiry date of %s" % expire_date)
        invitation.expiryTime = calendar.timegm(expire_date.timetuple())

    return invitation


def expiry_date(expiry):
    return datetime.datetime.utcnow() + expiry


def create_site_invitation(args=None):
    arg_parser = argparse.ArgumentParser(description="Create an invitation to a site for a given user.")

    arg_parser.add_argument('email', help="The email associated with the receiver for this invitation.")
    arg_parser.add_argument('site', help="The site to which the user will be invited")

    arg_parser.add_argument('--realname',
                            dest='realname',
                            action='store',
                            help="The realname of the receiver for this invitation.")

    arg_parser.add_argument('--admin',
                            dest='admin',
                            action='store_true',
                            default=False,
                            help="Whether this is an invitation for a site admin.")

    arg_parser.add_argument('--expiry',
                            dest='expiry',
                            action='store',
                            type=parse_time,
                            help="How long until token expires, e.g. \"1d\", \"4h\", or \"10m\"")

    arg_parser.add_argument('--devmode',
                            dest='devmode',
                            action='store_true',
                            default=False,
                            help="Dev mode")

    arg_parser.add_argument('--json',
                            dest='as_json',
                            action='store_true',
                            default=False,
                            help="Output full invitation as json.")

    arg_parser.add_argument('-v', '--verbose', help="Be verbose",
                            action='store_true', dest='verbose')

    args = arg_parser.parse_args(args=args)
    config_features = ('devmode',) if args.devmode else ()

    env_dir = os.getenv('DATASERVER_DIR')
    if not env_dir or not os.path.exists(env_dir) and not os.path.isdir(env_dir):
        print("Invalid dataserver environment root directory", env_dir)
        sys.exit(2)

    package = 'nti.appserver'
    # By default, we load all package-includes slugs
    context = create_context(env_dir, config_features)

    run_with_dataserver(environment_dir=env_dir,
                        xmlconfig_packages=(package,'nti.app.invitations'),
                        context=context,
                        verbose=args.verbose,
                        minimal_ds=True,
                        function=lambda: _create_site_invitation(args.email,
                                                                 args.realname,
                                                                 args.site,
                                                                 args.admin,
                                                                 args.expiry,
                                                                 as_json=args.as_json))


def main(args=None):
    create_site_invitation(args)
    sys.exit(0)


if __name__ == '__main__':
    main()
