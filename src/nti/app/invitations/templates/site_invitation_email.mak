TO: ${receiver_name}

% if brand:
	WEBSITE: ${brand}
% endif

% if redemption_link:
	ACCEPT INVITATION: ${redemption_link}
% endif

% if brand_message:
	${brand_message}
% endif

% if not brand_message:
	Congratulations! Enjoy full access to an interactive online platform like no other.
% endif

If you feel this email was sent in error, you may email ${support_email}.
