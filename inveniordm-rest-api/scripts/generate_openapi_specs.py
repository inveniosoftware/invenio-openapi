#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2025 KTH Royal Institute of Technology.
# Copyright (C) 2025 CERN.
#
# Invenio-openapi is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""
InvenioRDM OpenAPI Specification Generator

This script generates a comprehensive OpenAPI specification for InvenioRDM by:
1. Discovering all available endpoints from the Flask application
2. Automatically detecting and registering Marshmallow schemas
3. Categorizing endpoints by functionality (records, drafts, communities, etc.)
4. Providing proper request/response examples with schema references
5. Following OpenAPI 3.0.3 best practices

Usage:
    python invenio_openapi_generator.py [output_file.yaml]

Or within InvenioRDM context:
    uv run invenio shell invenio_openapi_generator.py
"""

import importlib
import inspect
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import yaml
from apispec import APISpec
from apispec.ext.marshmallow import MarshmallowPlugin
from flask import Flask
from marshmallow import Schema as MarshmallowSchema
from werkzeug.routing import Rule

try:
    from invenio_app.factory import create_api
except ImportError:
    print("Error: This script must be run within an InvenioRDM environment")
    sys.exit(1)

# API Configuration Constants
OPENAPI_VERSION = "3.0.3"
API_VERSION = "13.0.0"
API_TITLE = "Invenio REST API"
API_DESCRIPTION = """## **Summary**

The following document is a reference guide for all the REST APIs that InvenioRDM exposes.

## **Resources**

- 📚 [Product documentation](https://inveniordm.docs.cern.ch)
- 🔗 [OpenAPI GitHub repository](https://github.com/inveniosoftware/invenio-openapi)
- 🌐 [Invenio project](https://inveniosoftware.org)
- 💬 [Community support](https://inveniordm-dev.docs.cern.ch/install/troubleshoot/)
"""


@dataclass
class EndpointMetadata:
    """Metadata for a discovered endpoint."""

    path: str
    methods: Set[str]
    rule: Rule
    view_function: Any
    category: str
    schema_hint: Optional[str] = None
    description: Optional[str] = None


class SchemaDiscovery:
    """Discovers and manages Marshmallow schemas from InvenioRDM modules."""

    # Known InvenioRDM modules that contain schema definitions
    INVENIO_SCHEMA_MODULES = [
        # Core RDM schemas
        "invenio_rdm_records.services.schemas",
        "invenio_rdm_records.services.schemas.files",
        "invenio_rdm_records.services.schemas.parent",
        "invenio_rdm_records.services.schemas.access",
        "invenio_rdm_records.services.schemas.metadata",
        # Communities
        "invenio_communities.services.schemas",
        "invenio_communities.communities.schema",
        "invenio_communities.members.services.schemas",
        # Users and accounts
        "invenio_accounts.services.schemas",
        "invenio_users_resources.services.schemas",
        # Requests and workflows
        "invenio_requests.services.schemas",
        "invenio_requests.customizations.schemas",
        # Vocabularies
        "invenio_vocabularies.services.schema",
        "invenio_vocabularies.services.schemas",
        # Files and records resources
        "invenio_records_resources.services.schemas",
        "invenio_records_resources.services.files.schema",
        "invenio_records_resources.services.records.schema",
        # Additional services
        "invenio_jobs.services.schema",
        "invenio_search.services.schemas",
        "invenio_oaiserver.services.schemas",
        "invenio_statistics.services.schemas",
        "invenio_notifications.services.schemas",
    ]

    def __init__(self):
        self.schemas: Dict[str, type] = {}
        self.schema_categories: Dict[str, str] = {}
        self._discover_schemas()

    def _discover_schemas(self) -> None:
        """Discover all Marshmallow schemas from known modules."""
        for module_name in self.INVENIO_SCHEMA_MODULES:
            try:
                module = importlib.import_module(module_name)
                self._extract_schemas_from_module(module, module_name)
            except ImportError:
                # Module not available in this InvenioRDM installation
                continue
            except (AttributeError, TypeError) as e:
                print(f"Warning: Error loading schemas from {module_name}: {e}")
                continue

    def _extract_schemas_from_module(self, module: Any, module_name: str) -> None:
        """Extract schema classes from a module."""
        # Determine category from module name
        category = self._categorize_module(module_name)

        for name in dir(module):
            obj = getattr(module, name)
            if (
                inspect.isclass(obj)
                and issubclass(obj, MarshmallowSchema)
                and obj is not MarshmallowSchema
            ):
                # Store schema with clean name (avoid duplicates)
                clean_name = self._clean_schema_name(name)
                if clean_name not in self.schemas:
                    self.schemas[clean_name] = obj
                    self.schema_categories[clean_name] = category

                # Also store with original name if different (avoid duplicates)
                if clean_name != name and name not in self.schemas:
                    self.schemas[name] = obj
                    self.schema_categories[name] = category

    def _categorize_module(self, module_name: str) -> str:
        """Categorize module by its name."""
        if "rdm_records" in module_name:
            return "Records"
        elif "communities" in module_name:
            return "Communities"
        elif "users" in module_name or "accounts" in module_name:
            return "Users"
        elif "requests" in module_name:
            return "Requests"
        elif "vocabularies" in module_name:
            return "Vocabularies"
        elif "files" in module_name:
            return "Files"
        elif "jobs" in module_name:
            return "Jobs"
        elif "oai" in module_name:
            return "OAI-PMH"
        elif "notifications" in module_name:
            return "Notifications"
        elif "statistics" in module_name:
            return "Statistics"
        else:
            return "Core"

    def _clean_schema_name(self, name: str) -> str:
        """Clean schema name by removing 'Schema' suffix if present."""
        if name.endswith("Schema") and len(name) > 6:
            return name[:-6]
        return name

    def find_schema(self, hint: str) -> Optional[str]:
        """Find a schema name based on a hint (e.g., from URL path)."""
        # Direct lookup
        if hint in self.schemas:
            return hint

        # Try with Schema suffix
        schema_name = f"{hint}Schema"
        if schema_name in self.schemas:
            return schema_name

        # Case-insensitive search
        hint_lower = hint.lower()
        for schema_name in self.schemas:
            if schema_name.lower() == hint_lower:
                return schema_name

        # Fuzzy matching
        for schema_name in self.schemas:
            if hint_lower in schema_name.lower() or schema_name.lower() in hint_lower:
                return schema_name

        return None


class EndpointAnalyzer:
    """Analyzes Flask routes to extract endpoint information."""

    # Endpoint categorization patterns
    CATEGORY_PATTERNS = {
        "Records": [r"/records", r"/api/records"],
        "Drafts": [r"/records/.*draft", r"/api/records/.*draft"],
        "Communities": [r"/communities", r"/api/communities"],
        "Users": [r"/users", r"/api/users", r"/accounts"],
        "Requests": [r"/requests", r"/api/requests"],
        "Vocabularies": [r"/vocabularies", r"/api/vocabularies"],
        "Files": [r"/files", r"/api/files"],
        "Statistics": [r"/stats", r"/api/stats"],
        "OAI-PMH": [r"/oai", r"/api/oai"],
        "Jobs": [r"/jobs", r"/api/jobs"],
        "Search": [r"/search", r"/api/search"],
    }

    def __init__(self, schema_discovery: SchemaDiscovery):
        self.schema_discovery = schema_discovery

    def analyze_endpoints(self, app: Flask) -> List[EndpointMetadata]:
        """Analyze all endpoints in the Flask application."""
        endpoints = []

        for rule in app.url_map.iter_rules():
            # Skip static files and debug routes
            if self._should_skip_rule(rule):
                continue

            # Get HTTP methods (exclude HEAD and OPTIONS)
            methods = {m for m in rule.methods if m not in ("HEAD", "OPTIONS")}
            if not methods:
                continue

            # Convert Flask route to OpenAPI path
            openapi_path = self._flask_to_openapi_path(rule.rule)

            # Categorize endpoint
            category = self._categorize_endpoint(openapi_path)

            # Find schema hint
            schema_hint = self._extract_schema_hint(openapi_path)

            # Get view function
            view_function = app.view_functions.get(rule.endpoint)

            # Extract description from docstring if available
            description = self._extract_description(view_function)

            endpoint = EndpointMetadata(
                path=openapi_path,
                methods=methods,
                rule=rule,
                view_function=view_function,
                category=category,
                schema_hint=schema_hint,
                description=description,
            )

            endpoints.append(endpoint)

        return endpoints

    def _should_skip_rule(self, rule: Rule) -> bool:
        """Determine if a rule should be skipped."""
        skip_patterns = [
            r"^/static/",
            r"^/_debug",
            r"^/admin/static",
            r"^/favicon\.ico",
            r"^/robots\.txt",
        ]

        for pattern in skip_patterns:
            if re.match(pattern, rule.rule):
                return True

        return False

    def _flask_to_openapi_path(self, flask_path: str) -> str:
        """Convert Flask route format to OpenAPI path format."""
        # Convert <param> to {param} and <type:param> to {param}
        return re.sub(r"<(?:[^:]+:)?([^>]+)>", r"{\1}", flask_path)

    def _categorize_endpoint(self, path: str) -> str:
        """Categorize endpoint based on path patterns."""
        for category, patterns in self.CATEGORY_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, path, re.IGNORECASE):
                    return category
        return "Misc"

    def _extract_schema_hint(self, path: str) -> Optional[str]:
        """Extract schema hint from the endpoint path."""
        # Remove leading/trailing slashes and split
        parts = [p for p in path.strip("/").split("/") if p and not p.startswith("{")]

        if not parts:
            return None

        # Special mappings for known InvenioRDM patterns
        path_lower = path.lower()

        # Handle specific InvenioRDM endpoint patterns
        if "/communities" in path_lower:
            # For individual community operations use the main Community schema
            return "CommunitySchema"

        elif "/records" in path_lower:
            if "draft" in path_lower:
                return (
                    "RDMRecordSchema"  # Draft and published use same schema structure
                )
            else:
                return "RDMRecordSchema"  # Published record schema

        elif "/users" in path_lower or "/accounts" in path_lower:
            return "UserSchema"

        elif "/vocabularies" in path_lower:
            return "VocabularySchema"

        elif "/requests" in path_lower:
            return "RequestSchema"

        elif "/files" in path_lower:
            return "FileSchema"

        # Fallback to intelligent guessing
        hints = []

        # First non-api part
        if parts[0] == "api" and len(parts) > 1:
            hints.append(parts[1])
        else:
            hints.append(parts[0])

        # Last non-parameter part
        if len(parts) > 1:
            hints.append(parts[-1])

        # Try to find matching schema
        for hint in hints:
            # Handle plurals
            singular = self._singularize(hint)

            # Try different variations
            for variation in [hint, singular, hint.title(), singular.title()]:
                schema_name = self.schema_discovery.find_schema(variation)
                if schema_name:
                    return schema_name

        return None

    def _singularize(self, word: str) -> str:
        """Simple singularization."""
        if word.endswith("ies"):
            return word[:-3] + "y"
        elif word.endswith("s") and len(word) > 1:
            return word[:-1]
        return word

    def _extract_description(self, view_function: Any) -> Optional[str]:
        """Extract description from view function docstring."""
        if (
            view_function
            and hasattr(view_function, "__doc__")
            and view_function.__doc__
        ):
            # Take first line of docstring
            return view_function.__doc__.strip().split("\n")[0]
        return None


class OpenAPIGenerator:
    """Generates OpenAPI specification for InvenioRDM."""

    def __init__(self):
        self.schema_discovery = SchemaDiscovery()
        self.endpoint_analyzer = EndpointAnalyzer(self.schema_discovery)
        self.spec: Optional[APISpec] = None

    def generate(self, app: Flask) -> Dict[str, Any]:
        """Generate the complete OpenAPI specification."""
        with app.app_context():
            # Create APISpec instance
            self._create_spec(app)

            # Register all discovered schemas
            self._register_schemas()

            # Analyze endpoints
            endpoints = self.endpoint_analyzer.analyze_endpoints(app)

            # Generate paths
            self._generate_paths(endpoints)

            # Add tags
            self._add_tags(endpoints)

            # Convert to dict and post-process
            spec_dict = self.spec.to_dict()
            self._post_process_spec(spec_dict)

            # Apply sanitization to ensure YAML serializability
            spec_dict = self._sanitize_spec(spec_dict)

            return spec_dict

    def _create_spec(self, app: Flask) -> None:
        """Create the APISpec instance."""
        self.spec = APISpec(
            title=API_TITLE,
            version=API_VERSION,
            openapi_version=OPENAPI_VERSION,
            info={
                "description": API_DESCRIPTION,
                "contact": {
                    "name": "InvenioRDM Community",
                    "url": "https://inveniosoftware.org/",
                },
                "license": {
                    "name": "MIT",
                    "url": "https://opensource.org/licenses/MIT",
                },
            },
            servers=[
                {
                    "url": app.config.get("SITE_URL", "https://localhost:5000"),
                    "description": "InvenioRDM instance",
                }
            ],
            plugins=[MarshmallowPlugin()],
        )

    def _register_schemas(self) -> None:
        """Register all discovered schemas with the spec."""
        registered_schemas = set()

        for schema_name, schema_class in self.schema_discovery.schemas.items():
            # Skip if already registered
            if schema_name in registered_schemas:
                continue

            try:
                self.spec.components.schema(schema_name, schema=schema_class)
                registered_schemas.add(schema_name)
            except (ValueError, TypeError, AttributeError) as e:
                print(f"Warning: Could not register schema {schema_name}: {e}")
            except Exception as e:
                # Handle DuplicateComponentNameError and other apispec errors
                if "already registered" in str(e):
                    print(f"Info: Schema {schema_name} already registered, skipping")
                else:
                    print(f"Warning: Could not register schema {schema_name}: {e}")

    def _generate_paths(self, endpoints: List[EndpointMetadata]) -> None:
        """Generate path specifications for all endpoints."""
        # Group endpoints by path
        paths_by_route = defaultdict(list)
        for endpoint in endpoints:
            paths_by_route[endpoint.path].append(endpoint)

        for path, path_endpoints in paths_by_route.items():
            # Collect all methods for this path
            all_methods = set()
            for ep in path_endpoints:
                all_methods.update(ep.methods)

            # Get the best endpoint for schema hints (prefer GET)
            primary_endpoint = self._select_primary_endpoint(path_endpoints)

            operations = {}
            for method in all_methods:
                operation = self._create_operation(method, primary_endpoint)
                operations[method.lower()] = operation

            # Add path parameters
            path_params = self._extract_path_parameters(path)
            if path_params:
                for operation in operations.values():
                    operation.setdefault("parameters", []).extend(path_params)

            # Register path with spec
            try:
                self.spec.path(path=path, operations=operations)
            except (ValueError, TypeError) as e:
                print(f"Warning: Could not register path {path}: {e}")

    def _select_primary_endpoint(
        self, endpoints: List[EndpointMetadata]
    ) -> EndpointMetadata:
        """Select the primary endpoint for schema reference."""
        # Prefer GET, then POST, then others
        method_priority = {"GET": 0, "POST": 1, "PUT": 2, "PATCH": 3, "DELETE": 4}

        return min(
            endpoints,
            key=lambda ep: min(
                method_priority.get(method, 99) for method in ep.methods
            ),
        )

    def _create_operation(
        self, method: str, endpoint: EndpointMetadata
    ) -> Dict[str, Any]:
        """Create an operation specification for a method."""
        operation = {
            "tags": [endpoint.category],
            "summary": endpoint.description or f"{method} {endpoint.path}",
            "responses": {},
        }

        # Add query parameters for GET endpoints
        if method == "GET":
            query_params = self._get_query_parameters(endpoint)
            if query_params:
                operation["parameters"] = operation.get("parameters", []) + query_params

        # Add request body for write operations and specific endpoints
        if method in ("POST", "PUT", "PATCH") or self._needs_request_body(
            endpoint, method
        ):
            request_schema = self._get_request_schema(endpoint, method)
            if request_schema:
                operation["requestBody"] = {
                    "required": True,
                    "content": {"application/json": {"schema": request_schema}},
                }

        # Add responses
        if method == "DELETE":
            # DELETE endpoints return 204 No Content
            operation["responses"]["204"] = {"description": "No Content"}
        else:
            # Other methods return data
            response_schema = self._get_response_schema(endpoint)
            if response_schema:
                schema_ref = {"$ref": f"#/components/schemas/{response_schema}"}

                # For collection endpoints (GET without ID), return array
                if method == "GET" and not self._has_id_parameter(endpoint.path):
                    # Check if it's a search/collection endpoint that needs special handling
                    if any(
                        term in endpoint.path.lower()
                        for term in ["/search", "/communities", "/records", "/users"]
                    ):
                        # InvenioRDM typically returns paginated results
                        schema_ref = {
                            "type": "object",
                            "properties": {
                                "hits": {
                                    "type": "object",
                                    "properties": {
                                        "hits": {
                                            "type": "array",
                                            "items": {
                                                "$ref": f"#/components/schemas/{response_schema}"
                                            },
                                        },
                                        "total": {"type": "integer"},
                                    },
                                },
                                "links": {"type": "object"},
                                "aggregations": {"type": "object"},
                            },
                        }
                    else:
                        # Simple array for other collection endpoints
                        schema_ref = {"type": "array", "items": schema_ref}

                operation["responses"]["200"] = {
                    "description": "Successful response",
                    "content": {"application/json": {"schema": schema_ref}},
                }
            else:
                operation["responses"]["200"] = {"description": "Successful response"}

        # Add error responses
        operation["responses"]["400"] = {"description": "Bad Request"}
        operation["responses"]["401"] = {"description": "Unauthorized"}
        operation["responses"]["403"] = {"description": "Forbidden"}
        operation["responses"]["404"] = {"description": "Not Found"}
        operation["responses"]["500"] = {"description": "Internal Server Error"}

        return operation

    def _get_request_schema(
        self, endpoint: EndpointMetadata, method: str
    ) -> Optional[Dict[str, Any]]:
        """Get the appropriate schema for request body."""
        path_lower = endpoint.path.lower()

        # Authentication and user management endpoints
        if "/login" in path_lower and method == "POST":
            return {
                "type": "object",
                "properties": {
                    "email": {"type": "string", "format": "email"},
                    "password": {"type": "string"},
                    "remember": {"type": "boolean", "default": False},
                },
                "required": ["email", "password"],
            }

        elif "/register" in path_lower and method == "POST":
            return {
                "type": "object",
                "properties": {
                    "email": {"type": "string", "format": "email"},
                    "password": {"type": "string", "minLength": 8},
                    "password_confirm": {"type": "string", "minLength": 8},
                    "profile": {
                        "type": "object",
                        "properties": {
                            "full_name": {"type": "string"},
                            "affiliations": {"type": "string"},
                        },
                    },
                },
                "required": ["email", "password", "password_confirm"],
            }

        elif "/change-password" in path_lower and method == "POST":
            return {
                "type": "object",
                "properties": {
                    "current_password": {"type": "string"},
                    "new_password": {"type": "string", "minLength": 8},
                    "new_password_confirm": {"type": "string", "minLength": 8},
                },
                "required": [
                    "current_password",
                    "new_password",
                    "new_password_confirm",
                ],
            }

        elif "/forgot-password" in path_lower and method == "POST":
            return {
                "type": "object",
                "properties": {"email": {"type": "string", "format": "email"}},
                "required": ["email"],
            }

        elif "/reset-password" in path_lower and method == "POST":
            return {
                "type": "object",
                "properties": {
                    "token": {"type": "string"},
                    "password": {"type": "string", "minLength": 8},
                    "password_confirm": {"type": "string", "minLength": 8},
                },
                "required": ["token", "password", "password_confirm"],
            }

        elif "/send-confirmation-email" in path_lower and method == "POST":
            return {
                "type": "object",
                "properties": {"email": {"type": "string", "format": "email"}},
                "required": ["email"],
            }

        elif "/confirm-email" in path_lower and method == "POST":
            return {
                "type": "object",
                "properties": {"token": {"type": "string"}},
                "required": ["token"],
            }

        elif "/oauth" in path_lower and method == "POST":
            return {
                "type": "object",
                "properties": {"code": {"type": "string"}, "state": {"type": "string"}},
            }

        elif "/signup" in path_lower and method == "POST":
            return {
                "type": "object",
                "properties": {
                    "email": {"type": "string", "format": "email"},
                    "password": {"type": "string"},
                    "password_confirm": {"type": "string"},
                    "profile": {"type": "object"},
                },
                "required": ["email", "password", "password_confirm"],
            }

        # Content management endpoints
        elif "/banners" in path_lower and method == "POST":
            return {
                "type": "object",
                "properties": {
                    "message": {"type": "string"},
                    "category": {
                        "type": "string",
                        "enum": ["info", "warning", "error", "success"],
                    },
                    "start_datetime": {"type": "string", "format": "date-time"},
                    "end_datetime": {"type": "string", "format": "date-time"},
                    "url_path": {"type": "string"},
                    "active": {"type": "boolean", "default": True},
                },
                "required": ["message", "category"],
            }

        elif "/pages" in path_lower and method == "POST":
            return {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "content": {"type": "string"},
                    "template_name": {"type": "string"},
                    "url": {"type": "string"},
                    "description": {"type": "string"},
                },
                "required": ["title", "content", "url"],
            }

        elif "/stats" in path_lower and method == "POST":
            return {
                "type": "object",
                "properties": {
                    "views": {"type": "integer"},
                    "downloads": {"type": "integer"},
                    "recid": {"type": "string"},
                    "timestamp": {"type": "string", "format": "date-time"},
                },
            }

        elif "/vocabularies" in path_lower and method == "POST":
            if "/tasks" in path_lower:
                return {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string"},
                        "config": {"type": "object"},
                        "title": {"type": "string"},
                        "description": {"type": "string"},
                    },
                    "required": ["type"],
                }
            else:
                return {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "title": {
                            "type": "object",
                            "properties": {"en": {"type": "string"}},
                        },
                        "description": {
                            "type": "object",
                            "properties": {"en": {"type": "string"}},
                        },
                        "icon": {"type": "string"},
                        "props": {"type": "object"},
                        "tags": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["id", "title"],
                }

        # For regular endpoints, use schema reference if available
        elif endpoint.schema_hint:
            return {"$ref": f"#/components/schemas/{endpoint.schema_hint}"}

        return None

    def _get_response_schema(self, endpoint: EndpointMetadata) -> Optional[str]:
        """Get the appropriate schema for response body."""
        return endpoint.schema_hint

    def _needs_request_body(self, endpoint: EndpointMetadata, method: str) -> bool:
        """Check if an endpoint needs a request body beyond standard POST/PUT/PATCH."""
        path_lower = endpoint.path.lower()

        # Authentication and user management endpoints that need request bodies
        auth_endpoints = [
            "/login",
            "/signup",
            "/oauth",
            "/register",
            "/change-password",
            "/forgot-password",
            "/reset-password",
            "/send-confirmation-email",
            "/confirm-email",
        ]

        # Content management endpoints
        content_endpoints = ["/banners", "/pages", "/stats", "/vocabularies", "/tasks"]

        # Check for POST methods that need request bodies
        if method == "POST":
            # Auth endpoints
            if any(auth in path_lower for auth in auth_endpoints):
                return True

            # Content management endpoints
            if any(content in path_lower for content in content_endpoints):
                return True

            # Logout typically doesn't need a body in most implementations
            if "/logout" in path_lower:
                return False

        return False

    def _get_query_parameters(self, endpoint: EndpointMetadata) -> List[Dict[str, Any]]:
        """Get query parameters for an endpoint."""
        params = []
        path_lower = endpoint.path.lower()

        # Collection endpoints typically support search and pagination
        is_collection = not self._has_id_parameter(endpoint.path)

        if is_collection:
            # Common search parameters
            params.extend(
                [
                    {
                        "name": "q",
                        "in": "query",
                        "required": False,
                        "schema": {"type": "string"},
                        "description": "Search query",
                    },
                    {
                        "name": "sort",
                        "in": "query",
                        "required": False,
                        "schema": {"type": "string"},
                        "description": "Sort order (e.g., 'bestmatch', 'newest', 'oldest')",
                    },
                    {
                        "name": "size",
                        "in": "query",
                        "required": False,
                        "schema": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 100,
                            "default": 10,
                        },
                        "description": "Number of results per page",
                    },
                    {
                        "name": "page",
                        "in": "query",
                        "required": False,
                        "schema": {"type": "integer", "minimum": 1, "default": 1},
                        "description": "Page number",
                    },
                ]
            )

            # Specific parameters for different endpoints
            if "/communities" in path_lower:
                params.extend(
                    [
                        {
                            "name": "type",
                            "in": "query",
                            "required": False,
                            "schema": {"type": "string"},
                            "description": "Filter by community type",
                        },
                        {
                            "name": "featured",
                            "in": "query",
                            "required": False,
                            "schema": {"type": "boolean"},
                            "description": "Filter featured communities",
                        },
                    ]
                )

            elif "/records" in path_lower:
                params.extend(
                    [
                        {
                            "name": "type",
                            "in": "query",
                            "required": False,
                            "schema": {"type": "string"},
                            "description": "Filter by record type",
                        },
                        {
                            "name": "access",
                            "in": "query",
                            "required": False,
                            "schema": {
                                "type": "string",
                                "enum": ["public", "restricted"],
                            },
                            "description": "Filter by access level",
                        },
                        {
                            "name": "created",
                            "in": "query",
                            "required": False,
                            "schema": {"type": "string"},
                            "description": "Filter by creation date range",
                        },
                    ]
                )

            elif "/users" in path_lower:
                params.extend(
                    [
                        {
                            "name": "domain",
                            "in": "query",
                            "required": False,
                            "schema": {"type": "string"},
                            "description": "Filter by email domain",
                        }
                    ]
                )

        return params

    def _has_id_parameter(self, path: str) -> bool:
        """Check if path has an ID parameter."""
        return bool(re.search(r"\{[^}]*id[^}]*\}", path, re.IGNORECASE))

    def _extract_path_parameters(self, path: str) -> List[Dict[str, Any]]:
        """Extract path parameters from OpenAPI path."""
        params = []
        for match in re.finditer(r"\{([^}]+)\}", path):
            param_name = match.group(1)
            params.append(
                {
                    "name": param_name,
                    "in": "path",
                    "required": True,
                    "schema": {"type": "string"},
                    "description": f"The {param_name} identifier",
                }
            )
        return params

    def _add_tags(self, endpoints: List[EndpointMetadata]) -> None:
        """Add tags to the specification."""
        categories = set(ep.category for ep in endpoints)

        tag_descriptions = {
            "Records": "Published research records and publications",
            "Drafts": "Draft records before publication",
            "Communities": "Research communities and collections",
            "Users": "User accounts and profiles",
            "Requests": "Workflow requests and approvals",
            "Vocabularies": "Controlled vocabularies and taxonomies",
            "Files": "File management and storage",
            "Statistics": "Usage and download statistics",
            "OAI-PMH": "OAI-PMH metadata harvesting",
            "Jobs": "Background jobs and tasks",
            "Search": "Search and discovery",
            "Misc": "Miscellaneous endpoints",
        }

        for category in sorted(categories):
            self.spec.tag(
                {
                    "name": category,
                    "description": tag_descriptions.get(
                        category, f"{category} related operations"
                    ),
                }
            )

    def _post_process_spec(self, spec_dict: Dict[str, Any]) -> None:
        """Post-process the specification to fix any issues."""
        # Remove invalid schema types that might be added by Marshmallow
        self._fix_schema_types(spec_dict.get("components", {}).get("schemas", {}))

        # Sanitize the entire spec to make it YAML-serializable
        self._sanitize_spec(spec_dict)

    def _sanitize_spec(self, obj: Any) -> Any:
        """Recursively sanitize the spec to make it YAML-serializable."""
        if isinstance(obj, dict):
            result = {}
            for key, value in obj.items():
                # Convert keys to strings
                str_key = str(key)
                # Recursively sanitize values
                sanitized_value = self._sanitize_spec(value)
                if sanitized_value is not None:  # Skip None values
                    result[str_key] = sanitized_value
            return result
        elif isinstance(obj, list):
            return [
                self._sanitize_spec(item)
                for item in obj
                if self._sanitize_spec(item) is not None
            ]
        elif isinstance(obj, (str, int, float, bool)):
            return obj
        elif obj is None:
            return None
        else:
            # Handle special objects like marshmallow.missing
            try:
                # Try to convert to string representation
                str_repr = str(obj)
                # Skip marshmallow.missing and similar objects
                if "missing" in str_repr.lower() or "undefined" in str_repr.lower():
                    return None
                return str_repr
            except (AttributeError, ValueError, TypeError):
                return None

    def _fix_schema_types(self, schemas: Dict[str, Any]) -> None:
        """Fix invalid schema types in component schemas."""
        valid_types = {
            "array",
            "boolean",
            "integer",
            "number",
            "object",
            "string",
            "null",
        }

        def fix_node(node: Any) -> None:
            if isinstance(node, dict):
                # Fix invalid type values
                if "type" in node:
                    type_val = node["type"]
                    if type_val is None or type_val == "None":
                        # Remove None types completely
                        del node["type"]
                    elif isinstance(type_val, str) and type_val not in valid_types:
                        # If there's a $ref or composition keywords, remove type
                        if any(
                            key in node for key in ["$ref", "allOf", "anyOf", "oneOf"]
                        ):
                            del node["type"]
                        else:
                            node["type"] = "object"  # Safe fallback
                    elif not isinstance(type_val, str):
                        # Handle non-string types
                        if type_val is True or type_val is False:
                            node["type"] = "boolean"
                        elif isinstance(type_val, int):
                            node["type"] = "integer"
                        elif isinstance(type_val, float):
                            node["type"] = "number"
                        else:
                            del node["type"]  # Remove invalid types

                # Handle anyOf with None types
                if "anyOf" in node:
                    any_of = node["anyOf"]
                    if isinstance(any_of, list):
                        # Filter out None types and invalid entries
                        filtered_any_of = []
                        for item in any_of:
                            if isinstance(item, dict):
                                if "type" in item and (
                                    item["type"] is None or item["type"] == "None"
                                ):
                                    continue  # Skip None types
                                filtered_any_of.append(item)

                        if filtered_any_of:
                            node["anyOf"] = filtered_any_of
                        else:
                            # If no valid anyOf items, remove the anyOf
                            del node["anyOf"]

                # Recursively fix nested nodes
                for value in node.values():
                    fix_node(value)

            elif isinstance(node, list):
                for item in node:
                    fix_node(item)

        fix_node(schemas)


def main(filename: str = "openapi_generated.yaml") -> None:
    """Main function to generate OpenAPI specification."""
    try:
        # Create InvenioRDM application
        print("Creating InvenioRDM application...")
        app = create_api()

        # Generate OpenAPI spec
        print("Discovering schemas and endpoints...")
        generator = OpenAPIGenerator()
        spec_dict = generator.generate(app)

        # Validate the specification (basic check)
        print("Validating OpenAPI specification...")
        try:
            # Basic validation - check required fields
            required_fields = ["openapi", "info", "paths"]
            for field in required_fields:
                if field not in spec_dict:
                    raise ValueError(f"Missing required field: {field}")
            print("✅ OpenAPI specification basic validation passed")
        except (ValueError, TypeError) as e:
            print(f"⚠️  OpenAPI specification validation warning: {e}")

        # Write to file
        output_path = Path(filename)
        print(f"Writing specification to {output_path}...")

        # Copyright header for the YAML file
        yaml_header = """# -*- coding: utf-8 -*-
#
# Copyright (C) 2025 KTH Royal Institute of Technology.
# Copyright (C) 2025 CERN.
#
# Invenio-openapi is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""

        with open(output_path, "w", encoding="utf-8") as f:
            # Write copyright header first
            f.write(yaml_header)
            # Then write the YAML content
            yaml.safe_dump(
                spec_dict,
                f,
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=False,
            )

        # Print summary
        num_paths = len(spec_dict.get("paths", {}))
        num_schemas = len(spec_dict.get("components", {}).get("schemas", {}))
        print("✅ Generated OpenAPI specification:")
        print(f"   📄 {num_paths} endpoints")
        print(f"   📋 {num_schemas} schemas")
        print(f"   💾 Saved to: {output_path}")

    except (ImportError, RuntimeError, ValueError) as e:
        print(f"❌ Error generating OpenAPI specification: {e}")
        sys.exit(1)


if __name__ == "__main__":
    # Get output file from command line arguments
    output_file = sys.argv[1] if len(sys.argv) > 1 else "openapi_generated.yaml"
    main(output_file)
