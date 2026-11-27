# IMS V4.27.1 — new, user-supplied fonts

The complete application ZIP intentionally contains **no font binaries**. To activate the two fonts you provided, place your own copies in this folder under these EXACT file names:

1. `SC_DUBAI.ttf` — primary Arabic headlines on Home, Login, legal pages, and main dashboard headings.
2. `VIP Rawy Thin Thin.otf` — large, light-weight Arabic hero accent/section-kicker text.

The files must be included in your PRIVATE GitHub repository when Railway deploys. The browser requests these URLs:

- `https://YOUR-DOMAIN/static/fonts/SC_DUBAI.ttf`
- `https://YOUR-DOMAIN/static/fonts/VIP%20Rawy%20Thin%20Thin.otf`

A successful response contains font data, not a 404 or homepage HTML. Your server's network controls must permit these assets. On deployment, clear the browser cache (Ctrl+Shift+R). The site falls back to Cairo if either file is absent.

Other old fonts (`Amine_mod.ttf` and `banda.ttf`) are no longer referenced in the styles. You may remove them from your own repo after confirming everything works.

Please host these files only if you have the relevant font usage and web-embedding rights.
