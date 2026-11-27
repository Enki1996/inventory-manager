# IMS V4.25.1 — Arabic typography fix

## Why V4.25 displayed unchanged fonts

The V4.25 `marketing.css` declared the optional custom fonts but the downloadable ZIP contained only `static/fonts/README.md`. The browser could not fetch the `.ttf` assets and therefore rendered the fallback Arabic font. In addition, the fallback for some headings was an ordinary system font, creating little visual distinction.

## What changed

- Arabic hero and section headings now use **Amine_mod** when you provide the font file, otherwise the **Changa** webfont.
- Small eyebrow labels use **banda** when provided, otherwise **Marhey**.
- Medium card headlines use **Changa** and descriptive paragraphs continue to use **Cairo**.
- Bilingual legal pages receive the same heading hierarchy; the warehouse dashboard and forms keep readable system fonts.
- Font loading uses proper `@font-face` definitions and versioned paths to avoid stale browser cache. All frontend asset links are cache-busted with `?v=4.25.1`.
- Added deployment check script to validate private font uploads.
- The application release is 4.25.1; **Schema V10 remains unchanged**. No new migration and no database restoration required.

## Activate your exact uploaded fonts

1. Extract `Hospital_Warehouse_IMS_V4_25_1_FontFix_Railway.zip`.
2. Copy your own `Amine_mod.ttf` and `banda.ttf` to `static/fonts/` in the extracted project.
3. Upload/commit the entire source folder, including those two files, to your **private** GitHub repository.
4. Redeploy the same Railway service, preserving the existing `/data` volume and Railway environment variables.
5. Open `/static/fonts/Amine_mod.ttf` and `/static/fonts/banda.ttf` on your Railway domain, or run `python check_font_deployment.py https://YOUR-DOMAIN`.
6. Open the home page and hard-refresh. Check `/api/health` for `release: 4.25.1`, `version: 10`.

The source ZIP **does not contain the TTF files**. Do not upload B-Arabic-Style-1.ttf, which was intentionally not selected.

## Data safety

This is a frontend typography and release-label update. All existing Undo/Redo and Google Drive backup code remains as in V4.25. Never delete or replace the Railway `/data` volume as part of a code update; export a database backup first.
