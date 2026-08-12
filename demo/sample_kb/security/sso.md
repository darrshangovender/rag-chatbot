# Single Sign-On (SSO)

SAML 2.0 SSO is available on Business and Enterprise plans.

## Supported IdPs

We have pre-built setup guides for Okta, Microsoft Entra ID (formerly Azure AD), Google Workspace, OneLogin, and JumpCloud. Any SAML 2.0-compliant IdP will work; the generic setup is documented at **Settings → Security → SSO → Generic SAML**.

## Setup

1. In your IdP, create a new SAML application with these parameters:
   - **ACS URL**: `https://app.cumulus.example/saml/acs/<workspace-slug>`
   - **Entity ID**: `https://app.cumulus.example/saml/metadata/<workspace-slug>`
   - **NameID format**: EmailAddress
2. Map the following IdP attributes to SAML assertions: `email` (required), `firstName`, `lastName`.
3. In Cumulus, paste your IdP's metadata XML at **Settings → Security → SSO**.
4. Click **Test connection** to run a dry-run login.

## Enforcement

Once SSO is verified, you can require it under **Settings → Security → SSO enforcement**. Three modes:

- **Off** — users may sign in via SSO or with email + password.
- **Allowed** — users at allowed email domains must use SSO; everyone else can use password.
- **Required** — all users must use SSO; password sign-in is disabled workspace-wide.

The workspace owner is always exempt from "Required" mode as a break-glass — even if your IdP is down, the owner can still get in.

## Just-in-time provisioning

When a new user signs in via SSO with an email at an allowed domain, Cumulus creates the user account automatically with the default role (Member). For automatic group-to-team mapping, use SCIM.
