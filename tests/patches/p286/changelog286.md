## 1.0.286 — 16 November 2026

Fixed
- **Signing in with a certificate, the card watched: an iPad no longer signed out with its card in** - Safari on iPadOS signs nothing for a page in the background, so the check never arrived and the first one counted as the card taken out (found on a real iPad; the kit *card-removal-watch*, 3rd edition). A session now keeps whether a check in the background has ever found its card in this browser: never yet - *this browser cannot be checked*; found once - a check without it is a card taken out, as always. New setting **A browser that cannot be checked** (`admin_cert_card_unable`): `allow` (the default) - that sign-in is not watched, an event says so and why and the page tells the person; `signout` - signed out as before. The check's picture says no cookie came (3 px) or this browser cannot be checked (4 px); `card-gone` carries why (`nopicture`, `nocookie`), so the events name the reason.

