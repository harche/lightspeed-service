"""Structured output schemas for agent SDK capability modes.

Three phase-aligned schemas cover the full lifecycle:
  ANALYSIS  — covers design, remediate-analysis, and monitor
  EXECUTION — covers deploy and remediate-execution
  VERIFICATION — independent post-execution verification

Escalation retains a separate schema because its output shape
(support case report, KB search, GitHub issue) is unique.

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


# --- Analysis schema (design + remediate-analysis + monitor) ---

ANALYSIS_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "analysis": {
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
                "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
                "evidence": {"type": "array", "items": _EVIDENCE_SCHEMA},
                "relatedResources": {"type": "array", "items": _RESOURCE_REF_SCHEMA},
                "diagnosis": {
                    "type": "object",
                    "description": "Present when analysing an alert or issue",
                    "properties": {
                        "rootCause": {"type": "string"},
                        "confidence": {
                            "type": "string",
                            "enum": ["low", "medium", "high"],
                        },
                    },
                    "required": ["rootCause", "confidence"],
                },
                "proposal": {
                    "type": "object",
                    "description": "Proposed action — remediation or new deployment",
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
                        "risk": {
                            "type": "string",
                            "enum": ["low", "medium", "high"],
                        },
                        "reversible": {"type": "boolean"},
                        "estimatedImpact": {"type": "string"},
                    },
                    "required": ["description", "actions"],
                },
                "healthStatus": {
                    "type": "string",
                    "description": "Present for monitoring checks",
                    "enum": ["healthy", "degraded", "critical"],
                },
                "resources": {
                    "type": "array",
                    "description": "Resources inspected during analysis",
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
                    "description": "Metrics gathered during analysis",
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
                "risks": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
            "required": ["summary", "evidence"],
        },
    },
    "required": ["analysis"],
}


# --- Execution schema (deploy + remediate-execution) ---

EXECUTION_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "result": {
            "type": "object",
            "properties": {
                "success": {"type": "boolean"},
                "namespace": {"type": "string"},
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
                "components": {
                    "type": "array",
                    "description": "Components deployed (for deployment tasks)",
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
                "verification": {
                    "type": "object",
                    "properties": {
                        "conditionImproved": {"type": "boolean"},
                        "allHealthy": {"type": "boolean"},
                        "summary": {"type": "string"},
                        "evidence": {"type": "array", "items": _EVIDENCE_SCHEMA},
                    },
                    "required": ["summary"],
                },
                "issues": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
            "required": ["success", "actionsTaken", "verification"],
        },
    },
    "required": ["result"],
}


# --- Verification schema ---

VERIFICATION_OUTPUT_SCHEMA: dict[str, Any] = {
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


# --- Escalation schema (separate — unique workflow) ---

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


# Map mode constants to their output schemas for lookup.
# Multiple modes map to the same phase-aligned schema.
MODE_OUTPUT_SCHEMAS: dict[str, dict[str, Any]] = {
    constants.MODE_DESIGN: ANALYSIS_OUTPUT_SCHEMA,
    constants.MODE_MONITOR: ANALYSIS_OUTPUT_SCHEMA,
    constants.MODE_REMEDIATE: ANALYSIS_OUTPUT_SCHEMA,
    constants.MODE_DEPLOY: EXECUTION_OUTPUT_SCHEMA,
    constants.MODE_ESCALATE: ESCALATION_OUTPUT_SCHEMA,
    constants.MODE_VERIFY: VERIFICATION_OUTPUT_SCHEMA,
}
