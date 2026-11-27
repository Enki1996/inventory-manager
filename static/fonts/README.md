# Optional local Arabic headline fonts

The application works immediately using Changa and Marhey (served by Google Fonts) as public heading fallbacks. It **does not include your privately supplied TTF files**.

To activate your exact fonts, copy your own copies of these two files into this directory before uploading to your private GitHub repository:

- `Amine_mod.ttf` — main Arabic headlines
- `banda.ttf` — small accent headings

The filename must match letter-for-letter (Linux is case-sensitive). Both files must be committed to your GitHub repository for Railway to serve them. Do not add B-Arabic-Style-1.ttf; it is not used.

After deployment, check `/static/fonts/Amine_mod.ttf` and `/static/fonts/banda.ttf` in the browser. They should load as fonts, not as a 404 or the homepage HTML. Use the script `check_font_deployment.py https://your-domain.example` to validate the uploaded files.

Use fonts only if you hold the necessary rights to host them. The ZIP itself does not distribute any font binaries.
