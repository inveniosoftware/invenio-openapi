# Invenio/InvenioRDM OpenAPI documentation

This repository contains the OpenAPI specification for InvenioRDM and a static Swagger UI site.
At the moment, it is a manual effort.

## Accessing the API docs

The Swagger interface is available via GitHub Pages at <https://inveniosoftware.github.io/invenio-openapi/>.

By default, it is connected to the InvenioRDM demo website <https://inveniordm.web.cern.ch>. However, you can connect to your instance by changing the `baseURL` field in the web app.

## Preview Locally

Run a simple HTTP server from the repository root:

```bash
python3 -m http.server
```

Then open `http://localhost:8000/docs/` in your browser.

## Updating the OpenAPI Spec

Edit `docs/openapi.yaml` to update the API definition. The Swagger UI page automatically reflects any changes committed to this file.
