TO: ${receiver_name}
FROM: ${sender_name}

% if site_name:
	WEBSITE: ${site_name}
% endif

% if redemption_link:
	ACCEPT INVITATION: ${redemption_link}
% endif

% if invitation_message:
	${invitation_message}
% endif

% if not invitation_message:
	Congratulations! Enjoy full access to an interactive online platform like no other.
% endif

Access key: ${invitation_code}.

If you feel this email was sent in error, you may email ${support_email}.