# InvenioRDM OpenAPI Documentation

This repository contains the OpenAPI specification for InvenioRDM and a static Swagger UI site. 


## Accessing the API Documentation

The Swagger interface is available via GitHub Pages at <https://inveniosoftware.github.io/invenio-openapi/>.

By default, it connects to the InvenioRDM demo website <https://inveniordm.web.cern.ch>. However, you can connect to your own instance by changing the `baseURL` field in the web app.

## 🔧 Automated OpenAPI Spec Generation

This repository now includes automated generation of OpenAPI specifications directly from a live InvenioRDM instance.

### Quick Setup

```bash
# Clone and setup
git clone https://github.com/inveniosoftware/invenio-openapi.git
cd invenio-openapi

# Run automated setup (recommended)
./setup.sh
```

### Manual Setup

```bash
cd inveniordm-rest-api
uv venv                                                           # create virtual environment
source .venv/bin/activate                                         # activate it
uv pip install invenio-cli                                        # install invenio-cli
uv run invenio-cli install --pre                                  # install InvenioRDM
uv run invenio shell scripts/generate_spec.py                     # generate the spec
```

## Preview Locally

Run a simple HTTP server from the repository root:

```bash
python3 -m http.server
# Then open http://localhost:8000/docs/ in your browser
```

## Development & Contributing

### Updating Generation Scripts

The OpenAPI generation logic is in `inveniordm-rest-api/scripts/generate_spec.py`. When you modify this script:

1. **Test locally**: Run `./setup.sh` or the manual commands above
2. **Commit changes**: The CI will automatically regenerate specs
3. **Review generated specs**: Check the resulting `docs/openapi.yaml`
