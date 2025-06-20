# Invenio OpenAPI Documentation

This repository contains the OpenAPI specification for InvenioRDM and a static Swagger UI site.

## Viewing the API Docs

GitHub Pages serves the site from the `docs/` folder on the `main` branch. Once Pages is enabled in the repository settings, visit:

```
https://<your-github-username>.github.io/<repository-name>/
```

Replace `<your-github-username>` and `<repository-name>` with the appropriate values.

## Preview Locally

Run a simple HTTP server from the repository root:

```bash
python3 -m http.server
```

Then open `http://localhost:8000/docs/` in your browser.

## Updating the OpenAPI Spec

Edit `rdm/openapi.yaml` to update the API definition. The Swagger UI page automatically reflects any changes committed to this file.
