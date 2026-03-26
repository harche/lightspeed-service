"""Structured output schemas for agent SDK capability modes.

These JSON schemas can be passed to Claude's structured output feature to ensure
responses conform to a predictable shape for downstream processing
(operator reconcilers, console UI rendering, etc.).
"""

from typing import Any

from ols import constants

# Shared sub-schemas used across multiple mode schemas

_EVIDENCE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "type": {"type": "string", "description": "metric, event, log, or resource"},
        "source": {"type": "string", "description": "Where the evidence came from"},
        "value": {"type": "string", "description": "The observed value"},
    },
    "required": ["type", "source", "value"],
}

_RESOURCE_REF_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "apiVersion": {"type": "string"},
        "kind": {"type": "string"},
        "name": {"type": "string"},
        "namespace": {"type": "string"},
    },
    "required": ["kind", "name"],
}


# --- Design mode schema ---

DESIGN_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "proposal": {
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
                "operators": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "packagemanifest name",
                            },
                            "displayName": {"type": "string"},
                            "channel": {
                                "type": "string",
                                "description": "subscription channel",
                            },
                            "catalogSource": {"type": "string"},
                            "installed": {"type": "boolean"},
                            "purpose": {"type": "string"},
                        },
                        "required": [
                            "name",
                            "displayName",
                            "channel",
                            "catalogSource",
                            "installed",
                            "purpose",
                        ],
                    },
                },
                "operatorCRs": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "apiVersion": {"type": "string"},
                            "kind": {"type": "string"},
                            "name": {"type": "string"},
                            "purpose": {"type": "string"},
                            "keyFields": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "path": {"type": "string"},
                                        "value": {"type": "string"},
                                        "description": {"type": "string"},
                                    },
                                    "required": ["path", "value", "description"],
                                },
                            },
                        },
                        "required": ["apiVersion", "kind", "name", "purpose", "keyFields"],
                    },
                },
                "appComponents": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "kind": {"type": "string"},
                            "description": {"type": "string"},
                            "port": {"type": "integer"},
                            "dependencies": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                        },
                        "required": ["name", "kind", "description"],
                    },
                },
                "infraResources": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "kind": {"type": "string"},
                            "name": {"type": "string"},
                            "purpose": {"type": "string"},
                        },
                        "required": ["kind", "name", "purpose"],
                    },
                },
                "risks": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
            "required": [
                "summary",
                "operators",
                "operatorCRs",
                "appComponents",
                "infraResources",
            ],
        },
    },
    "required": ["proposal"],
}


# --- Deploy mode schema ---

DEPLOY_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "result": {
            "type": "object",
            "properties": {
                "success": {"type": "boolean"},
                "namespace": {"type": "string"},
                "components": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "kind": {"type": "string"},
                            "ready": {"type": "boolean"},
                            "image": {"type": "string"},
                        },
                        "required": ["name", "kind", "ready"],
                    },
                },
                "issues": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
            "required": ["success", "components"],
        },
    },
    "required": ["result"],
}


# --- Monitor mode schema ---

MONITOR_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "health": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["healthy", "degraded", "critical"],
                },
                "component": {"type": "string"},
                "namespace": {"type": "string"},
                "resources": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "kind": {"type": "string"},
                            "name": {"type": "string"},
                            "status": {"type": "string"},
                            "restarts": {"type": "integer"},
                        },
                        "required": ["kind", "name", "status"],
                    },
                },
                "metrics": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "metric": {"type": "string"},
                            "value": {"type": "string"},
                            "threshold": {"type": "string"},
                            "status": {
                                "type": "string",
                                "enum": ["ok", "warning", "critical"],
                            },
                        },
                        "required": ["metric", "value", "status"],
                    },
                },
                "findings": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "observation": {"type": "string"},
                            "requiresAction": {"type": "boolean"},
                            "recommendation": {"type": "string"},
                        },
                        "required": ["observation", "requiresAction"],
                    },
                },
                "recommendation": {"type": "string"},
            },
            "required": ["status", "component", "resources", "findings", "recommendation"],
        },
    },
    "required": ["health"],
}


# --- Remediate analysis schema ---

REMEDIATE_ANALYSIS_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "diagnosis": {
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
                "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
                "rootCause": {"type": "string"},
                "evidence": {"type": "array", "items": _EVIDENCE_SCHEMA},
                "relatedResources": {"type": "array", "items": _RESOURCE_REF_SCHEMA},
            },
            "required": ["summary", "confidence", "rootCause", "evidence", "relatedResources"],
        },
        "proposal": {
            "type": "object",
            "properties": {
                "description": {"type": "string"},
                "actions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {"type": "string"},
                            "description": {"type": "string"},
                            "resource": _RESOURCE_REF_SCHEMA,
                            "patch": {"type": "string"},
                        },
                        "required": ["type", "description"],
                    },
                },
                "risk": {"type": "string", "enum": ["low", "medium", "high"]},
                "reversible": {"type": "boolean"},
                "estimatedImpact": {"type": "string"},
            },
            "required": ["description", "actions", "risk", "reversible"],
        },
    },
    "required": ["diagnosis", "proposal"],
}


# --- Remediate execution schema ---

REMEDIATE_EXECUTION_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "result": {
            "type": "object",
            "properties": {
                "success": {"type": "boolean"},
                "actionsTaken": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {"type": "string"},
                            "description": {"type": "string"},
                            "resource": _RESOURCE_REF_SCHEMA,
                            "success": {"type": "boolean"},
                            "output": {"type": "string"},
                            "error": {"type": "string"},
                        },
                        "required": ["type", "description", "success"],
                    },
                },
                "verification": {
                    "type": "object",
                    "properties": {
                        "conditionImproved": {"type": "boolean"},
                        "summary": {"type": "string"},
                        "evidence": {"type": "array", "items": _EVIDENCE_SCHEMA},
                    },
                    "required": ["conditionImproved", "summary", "evidence"],
                },
            },
            "required": ["success", "actionsTaken", "verification"],
        },
    },
    "required": ["result"],
}


# --- Escalation schema ---

ESCALATION_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "report": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "severity": {"type": "integer", "enum": [1, 2, 3, 4]},
                "product": {"type": "string"},
                "version": {"type": "string"},
                "component": {"type": "string"},
                "environment": {
                    "type": "object",
                    "properties": {
                        "clusterID": {"type": "string"},
                        "platform": {"type": "string"},
                        "nodeCount": {"type": "integer"},
                    },
                    "required": ["clusterID", "platform", "nodeCount"],
                },
                "description": {"type": "string"},
                "stepsToReproduce": {"type": "string"},
                "remediationAttempted": {"type": "string"},
                "kbSearchResults": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "url": {"type": "string"},
                            "title": {"type": "string"},
                            "relevant": {"type": "boolean"},
                        },
                        "required": ["url", "title", "relevant"],
                    },
                },
                "duplicateSearch": {
                    "type": "object",
                    "properties": {
                        "searched": {"type": "boolean"},
                        "duplicateFound": {"type": "boolean"},
                        "duplicateURL": {"type": "string"},
                    },
                    "required": ["searched", "duplicateFound"],
                },
            },
            "required": [
                "title",
                "severity",
                "product",
                "version",
                "component",
                "environment",
                "description",
                "stepsToReproduce",
                "remediationAttempted",
                "kbSearchResults",
                "duplicateSearch",
            ],
        },
        "caseRef": {
            "type": "object",
            "properties": {
                "backend": {"type": "string"},
                "url": {"type": "string"},
                "id": {"type": "string"},
            },
            "required": ["backend", "url", "id"],
        },
    },
    "required": ["report", "caseRef"],
}


# --- Verify mode schema ---

VERIFY_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "verification": {
            "type": "object",
            "properties": {
                "result": {
                    "type": "string",
                    "enum": ["PASSED", "FAILED"],
                },
                "confidence": {
                    "type": "string",
                    "enum": ["high", "medium", "low"],
                },
                "checks": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "description": {"type": "string"},
                            "expected": {"type": "string"},
                            "actual": {"type": "string"},
                            "passed": {"type": "boolean"},
                        },
                        "required": ["description", "expected", "actual", "passed"],
                    },
                },
                "evidence": {"type": "array", "items": _EVIDENCE_SCHEMA},
                "issues": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
            "required": ["result", "confidence", "checks", "evidence"],
        },
    },
    "required": ["verification"],
}


# Map mode constants to their output schemas for lookup.
# MODE_REMEDIATE maps to the analysis schema by default; the execution
# schema is used when the operator transitions to the execution phase.
MODE_OUTPUT_SCHEMAS: dict[str, dict[str, Any]] = {
    constants.MODE_DESIGN: DESIGN_OUTPUT_SCHEMA,
    constants.MODE_DEPLOY: DEPLOY_OUTPUT_SCHEMA,
    constants.MODE_MONITOR: MONITOR_OUTPUT_SCHEMA,
    constants.MODE_REMEDIATE: REMEDIATE_ANALYSIS_OUTPUT_SCHEMA,
    constants.MODE_ESCALATE: ESCALATION_OUTPUT_SCHEMA,
    constants.MODE_VERIFY: VERIFY_OUTPUT_SCHEMA,
}
