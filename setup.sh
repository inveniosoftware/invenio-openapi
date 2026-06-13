#!/bin/bash
set -e

echo "🚀 Setting up InvenioRDM OpenAPI Generator"
echo "=========================================="

# Change to the InvenioRDM instance directory
cd inveniordm-rest-api

echo "📦 Creating virtual environment..."
uv venv

echo "🔧 Activating virtual environment..."
source .venv/bin/activate

echo "📚 Installing invenio-cli..."
uv pip install invenio-cli

echo "🏗️  Installing InvenioRDM..."
uv run invenio-cli install --pre

echo "🎯 Generating OpenAPI specification..."
uv run invenio shell scripts/generate_spec.py

echo ""
echo "✅ Setup complete!"
echo ""
echo "📄 Generated files:"
ls -la ../docs/openapi*.yaml || echo "No OpenAPI files found"
echo ""
echo "🔄 To regenerate specs manually:"
echo "   cd inveniordm-rest-api"
echo "   source .venv/bin/activate"
echo "   uv run invenio shell scripts/generate_spec.py"
echo ""
echo "🌐 View the specs at: https://inveniosoftware.github.io/invenio-openapi/"
