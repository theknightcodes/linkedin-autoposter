# Lessons Learned — LinkedIn Autoposter

---

## 1. `conda run` picks up system Python, not the env

**Problem:** `conda run -n linkedin-autoposter python` resolved to Homebrew Python 3.14 (on PATH) instead of the conda env's Python 3.11. Dependencies installed in the conda env were not found.

**Fix:** Always invoke the env's Python directly:
```
/opt/miniconda3/envs/linkedin-autoposter/bin/python
```

---

## 2. LinkedIn-Version header expires — use current YYYYMM

**Problem:** `LinkedIn-Version: 202404` returned HTTP 426 `NONEXISTENT_VERSION`. LinkedIn deactivates old API versions periodically.

**Fix:** Updated to `202601`. Format must be `YYYYMM` (not `YYYYMMDD`). Verify an active version by sending a request and checking for 401 (auth fail = version valid) vs 426 (version expired).

**Rule:** When LinkedIn API returns 426, bump `LinkedIn-Version` in `src/linkedin_client.py` to the current month.

---

## 3. `oauth_setup.py` was wiping `LINKEDIN_PERSON_URN` on every run

**Problem:** The profile fetch in OAuth setup fails (because `w_member_social` scope doesn't grant `/v2/me` access), so `_result["person_urn"]` is empty and `_write_env` overwrites the URN with an empty string.

**Fix:** Only write `LINKEDIN_PERSON_URN` to `.env` when a valid non-empty URN is fetched. Preserve existing value otherwise.

---

## 4. LinkedIn REST API uses alphanumeric Person URNs, not numeric

**Problem:** The old numeric ID `urn:li:person:94515370` (from legacy v2 API) returns HTTP 403 on the new `/rest/posts` endpoint. The REST API uses alphanumeric IDs.

**Fix:** The correct URN `urn:li:person:edM1EcVerD` was discovered from a 422 error response when trying `urn:li:member:94515370` — LinkedIn revealed the resolved alphanumeric URN in the error message.

**Rule:** If you see 403 on `/rest/posts`, check whether the Person URN is numeric (old format). Use `urn:li:member:<numeric_id>` in a test POST — the 422 error response will reveal the correct `urn:li:person:<alphanumeric>` URN.

---

## 5. LinkedIn 201 response has empty body — don't parse it as JSON

**Problem:** `resp.json()` on a successful 201 response threw `json.JSONDecodeError` (empty body). This was caught as a `requests.RequestException` (network error), causing a retry. The retry then hit LinkedIn's duplicate post detection (422).

**Fix:** Read the post URN from the `x-restli-id` response header. Only attempt `resp.json()` if `resp.text` is non-empty:
```python
urn = resp.headers.get("x-restli-id") or (resp.json().get("id", "unknown") if resp.text else "unknown")
```

---

## 6. OAuth profile fetch needs `/v2/userinfo`, not `/v2/me`

**Problem:** `oauth_setup.py` fetched profile via `/v2/me` which requires `r_liteprofile` scope. With only `w_member_social` granted, this returns 403 and the URN is never saved.

**Fix:** Try `/v2/userinfo` first (OpenID Connect endpoint, available when "Sign In with LinkedIn using OpenID Connect" product is added). It returns `sub` (alphanumeric person ID) and `given_name`/`family_name`. Fall back to `/v2/me` if that also fails.

---

## 7. "Share on LinkedIn" product is required for posting

**Problem:** HTTP 403 on `/rest/posts` even with a valid token. Root cause: the LinkedIn Developer App was missing the **"Share on LinkedIn"** product, which is the only product that grants `w_member_social` scope.

**Fix:** In the LinkedIn Developer Portal → App → Products tab → Request **"Share on LinkedIn"**. Then re-run `oauth_setup.py` to get a token with the correct scope.

**Note:** "Sign In with LinkedIn using OpenID Connect" is a separate product for authentication only — it does NOT grant posting permissions.
