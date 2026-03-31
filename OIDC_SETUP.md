# OIDC Authentication Setup Guide

This document describes the changes made to implement OIDC (OpenID Connect) authentication and what you need to do to complete the setup.

## Changes Made

### 1. Dependencies Updated
- **Removed**: `Flask-OpenID==1.3.1` and `django-openid-auth==0.17`
- **Added**: `Authlib==1.3.0`

### 2. Authentication System Rewritten
- Replaced Flask-OpenID with modern Authlib OIDC implementation
- Updated [webapp/sso.py](webapp/sso.py) with OIDC authentication flow
- Added backward compatibility for existing session structure

### 3. Code Updates
- Updated [webapp/app.py](webapp/app.py) to support both new and legacy session keys
- Maintained `session["openid"]` for backward compatibility

## Required Configuration

### Environment Variables
You **MUST** set the following environment variables in your `.env` file or deployment environment:

```bash
# OIDC Provider Configuration
OIDC_ISSUER=https://login.ubuntu.com
OIDC_CLIENT_ID=your_client_id_here
OIDC_CLIENT_SECRET=your_client_secret_here

# Optional Configuration
OIDC_SCOPES=openid profile email
OIDC_LOGOUT_URL=https://login.ubuntu.com/+logout

# Team/Group Requirement (existing variable, still used)
OPENID_LAUNCHPAD_TEAM=canonical-content-people
```

### Required Variables Explained

1. **OIDC_ISSUER** (Required)
   - The OIDC provider's base URL
   - Default: `https://login.ubuntu.com`
   - Must support OIDC Discovery (`.well-known/openid-configuration`)

2. **OIDC_CLIENT_ID** (Required)
   - Your application's client ID from the OIDC provider
   - You need to register your application with the OIDC provider

3. **OIDC_CLIENT_SECRET** (Required)
   - Your application's client secret from the OIDC provider
   - Keep this secure and never commit to version control

4. **OIDC_SCOPES** (Optional)
   - Space-separated list of OAuth scopes
   - Default: `openid profile email`

5. **OIDC_LOGOUT_URL** (Optional)
   - URL for provider-side logout
   - If not set, only local session is cleared

6. **OPENID_LAUNCHPAD_TEAM** (Optional)
   - Team/group name required for access
   - Default: `canonical`
   - Set to your team: `canonical-content-people`

## Steps to Complete Setup

### 1. Register Your Application with the OIDC Provider

You need to register this application with your OIDC provider (likely login.ubuntu.com or a Canonical OIDC service):

**Registration Details:**
- **Application Name**: Library Canonical
- **Redirect URIs**: 
  - For local development: `http://localhost:8051/authorize`
  - For production: `https://library.canonical.com/authorize`
- **Scopes Required**: `openid profile email` (and potentially custom team/group scopes)

**Where to Register:**
- For login.ubuntu.com: Contact your system administrator or use the Canonical developer portal
- You may need to request access to team membership information in the OIDC claims

### 2. Update Environment Variables

Add the credentials from step 1 to your `.env` file:

```bash
echo "OIDC_CLIENT_ID=your_actual_client_id" >> .env
echo "OIDC_CLIENT_SECRET=your_actual_client_secret" >> .env
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Test Locally

```bash
flask run
```

Visit `http://localhost:8051/login` and verify:
- Redirects to OIDC provider
- After authentication, redirects back to your app
- User is logged in and can access protected pages
- Team membership is enforced

### 5. Update Production Deployment

Add the same environment variables to your production deployment:
- For Kubernetes: Update ConfigMap/Secrets
- For Juju/Charms: Update charm configuration
- For Docker: Update docker-compose.yml or runtime environment

## Team Membership Verification

The implementation checks for team membership in the OIDC user info response. The expected format depends on your OIDC provider:

- **Teams in 'teams' claim**: Array of team names or objects
- **Groups in 'groups' claim**: Array of group names
- **Custom claim**: May need modification based on your provider

If team membership checking doesn't work, you may need to:
1. Verify the OIDC provider includes team/group information in the userinfo endpoint
2. Update the `check_team_membership()` function in [webapp/sso.py](webapp/sso.py)
3. Request additional scopes or claims from your OIDC provider

## Troubleshooting

### Common Issues

1. **"Missing OIDC_CLIENT_ID" Error**
   - Ensure all required environment variables are set
   - Check `.env` file is loaded properly

2. **"Authentication failed" Error**
   - Verify redirect URI matches exactly what's registered
   - Check client ID and secret are correct
   - Ensure OIDC_ISSUER is correct and accessible

3. **"Access denied" (403) Error**
   - User is not in the required team
   - Check OPENID_LAUNCHPAD_TEAM matches your team name
   - Verify team information is included in OIDC claims

4. **Redirect Loop**
   - Check that `/authorize` route is in public routes (already handled in code)
   - Verify session cookies are being set properly
   - Check SECRET_KEY is set and persistent

### Debug Mode

Set `FLASK_DEBUG=true` to see detailed error messages and OAuth flow debugging:

```bash
export FLASK_DEBUG=true
flask run
```

## Migration from Old Authentication

The implementation maintains backward compatibility:
- `session["openid"]` is still populated for existing code
- `session["user"]` contains the new data structure
- Both session keys are checked in authentication middleware

No additional migration steps are needed for existing code.

## Security Considerations

1. **Never commit secrets**: Keep `OIDC_CLIENT_SECRET` in environment variables only
2. **Use HTTPS in production**: OIDC requires secure connections
3. **Rotate secrets regularly**: Update client secret periodically
4. **Validate redirect URIs**: Ensure only your domains are registered

## Additional Resources

- [Authlib Documentation](https://docs.authlib.org/en/latest/client/flask.html)
- [OpenID Connect Specification](https://openid.net/connect/)
- [Canonical SSO Documentation](https://login.ubuntu.com/)

## Support

If you encounter issues:
1. Check the troubleshooting section above
2. Review Authlib logs (enable Flask debug mode)
3. Contact Canonical IT for OIDC provider access/configuration
