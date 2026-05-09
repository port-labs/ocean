"""Routing layer: maps an EventBridge envelope to (kind, action, identifier).

Pure data — no I/O, no async. Tests should be cheap and deterministic.
"""
