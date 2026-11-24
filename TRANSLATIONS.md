# Editing Arabic and English terminology — V4.0

The site is **Arabic-first**; staff may switch to English from every page. The selection persists in their individual browser.

## Arabic language file

Open `static/locales/ar.json` with a text editor. Each entry has an existing English UI phrase on the left and its Arabic translation on the right. Example:

```json
"Paper requisition serial number": "الرقم التسلسلي لطلب التجهيز الورقي",
"Receive Shipments": "استلام الشحنات",
"Departments": "الأقسام"
```

Change **only the Arabic value** after the colon to customize a term. Save the file as UTF-8 without removing quotation marks or commas. Reload the browser page. Railway redeploys automatically after committing the changed file to the private GitHub repository.

## English terminology

English source labels appear in the HTML/JS page files under `static/`. If changing English source wording, update the matching key in `ar.json`. For general terminology updates, you can send us your desired English and Arabic phrases and we can edit the files together.

## Important behaviour

- Switching language is a **UI operation only**. It never changes the item, batch, staff or requisition data stored in the database.
- Arabic layouts use `dir="rtl"`, while English uses `dir="ltr"`. IDs, user-entered quantities, codes and dates remain usable.
- Navigation, titles, dynamic management forms, error notices and backup instructions are translated. Backend-originated validation errors may still appear in English when the API sends an unfamiliar error message; server-side localization can be added next.
- Medical product names and hospital department names created by staff are shown as entered. Bilingual names for saved records would require adding dedicated Arabic/English fields later.
- The sample Home page still contains planned placeholder links for its future Overview/Features/Workflow sections. This version translates those labels but does not create additional marketing pages.

## Deployment rules

Keep your existing Railway /data volume; update the **code**, not the database file. Configure a strong bootstrap admin password in Railway secrets as described in `RAILWAY_SETUP.md`. The old local testing password `123` must never be used on a public Railway deployment.
