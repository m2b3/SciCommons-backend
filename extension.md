# Browser extension Test identity and key

Last reviewed: 2026-08-24 UTC

## Relevant extension repository

The browser-extension client is maintained separately at:

- `m2b3/ExtensionSciCommons`

The remote repository does not yet contain the locally generated public-key change described
below. The private key must never be added to that repository or any SciCommons repository.

## Test extension identity

The current local extension uses this Chrome extension ID:

```text
gcoffiocepphklfgmpaclpkeejdamlld
```

The extension identifies its integration client as `scicommons-clipper`, which is already included
in the backend's default `INTEGRATION_ALLOWED_CLIENT_IDS` value.

The extension calls:

```javascript
chrome.identity.getRedirectURL("scicommons")
```

For the ID above, Chrome produces this callback URI:

```text
https://gcoffiocepphklfgmpaclpkeejdamlld.chromiumapp.org/scicommons
```

## Required Test configuration

Configure these values in the backend **Test runtime environment**:

```dotenv
INTEGRATION_CORS_ALLOWED_ORIGINS=chrome-extension://gcoffiocepphklfgmpaclpkeejdamlld
INTEGRATION_ALLOWED_REDIRECT_URIS=https://gcoffiocepphklfgmpaclpkeejdamlld.chromiumapp.org/scicommons
```

These are exact allowlist entries. Do not add a wildcard or trailing slash.

The frontend Test build uses:

```dotenv
NEXT_PUBLIC_BACKEND_URL=https://backendtest.scicommons.org
```

The frontend deployment workflow supplies that build variable from the GitHub secret named
`NEXT_PUBLIC_BACKEND_URL_TEST`. No separate frontend callback allowlist is needed.

These configuration values do not themselves deploy the integration code. The Test environments
must also contain the backend integration endpoints from backend PRs #167/#168 and the frontend
authorization pages from frontend PR #363.

## Public and private key handling

A local public/private key pair was created to give unpacked development copies a stable extension
ID. The public key is stored locally as the `"key"` value in `manifest.json`; that public manifest
change has not yet been pushed.

- The public key and extension ID are not secrets. The manifest's public `"key"` value may be
  committed and pushed when shared testing is needed.
- Never commit or push the private key or `.pem` file. Keep it outside the repository, restrict its
  permissions, and maintain a protected backup.
- Add the private-key filename or path to the extension repository's `.gitignore` before staging
  files.
- If the private key is ever exposed, replace the key pair. A replacement key changes the extension
  ID, so the backend allowlists must also be updated.

There is no requirement to push the public-key manifest change while only the current local checkout
is being used for testing. Push it later when another developer or machine must reproduce the same
unpacked extension ID.

## Verification before configuring or deploying

1. Load the local extension through `chrome://extensions` with Developer mode enabled.
2. Confirm Chrome displays `gcoffiocepphklfgmpaclpkeejdamlld`.
3. Confirm `chrome.identity.getRedirectURL("scicommons")` produces the callback URI documented
   above.
4. Confirm the private key is not staged or tracked before pushing the public manifest change.

For eventual Chrome Web Store publication, confirm the Developer Dashboard Item ID/public key
matches this Test identity before reusing the same allowlists for a published build. A different
store ID requires different backend CORS and redirect entries.
