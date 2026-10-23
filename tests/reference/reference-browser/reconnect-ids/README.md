# Reconnect with a supplied session id (Python 1.66.1)

Three WebSocket handshakes against the pinned Python 1.66.1 reference app, each
carrying a third subprotocol entry with the session id to resume.  The raw
`probe-result.json` is the captured result, kept byte for byte; its
sha256 is `91931df50407d63d734252f5fb047e8a40e08ab67de408c2d4c57b94de33c0df`.

| case | third subprotocol entry | handshake | session id returned |
|---|---|---|---|
| A | `11111111-2222-3333-4444-555555555555` (a valid but unknown UUID) | HTTP 101, `streamlit` | new: `20bc4587-de42-4f66-97a5-c240320890ae` |
| B | `unknown-session` (a legal protocol entry that is not a UUID) | HTTP 101, `streamlit` | new: `db5c768a-8eb9-4cf2-ab18-9f29abf3cfc6` |
| C | `0dd87851-dcad-4050-a30d-c943bcaa6c96` (the session that was active) | HTTP 101, `streamlit` | the same: `0dd87851-dcad-4050-a30d-c943bcaa6c96` |

The server does not validate the third entry at all: an unknown UUID and a
non-UUID string are both accepted and both start a **new** session, while the id
of a live session resumes that session.  No 400 and no 409 were observed on any
of the three handshakes.

**Limitation.**  This probe only records what the server answered.  Whether the
socket of the session that was already open stayed open, or was closed and
replaced when case C resumed it, was not observed: no close event was captured,
so the fate of the previous connection is not established here.

The handshake entries carry the reference app's own XSRF token and the local
absolute path of the reference script; both are local test material, not
credentials for anything outside this workspace.
