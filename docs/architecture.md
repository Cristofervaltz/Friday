# Architecture Notes

## Purpose

Friday v0.0.1 establishes a stable software foundation for a future desktop automation assistant.

## Current runtime behavior

The current runtime intentionally does only three things:

1. load configuration
2. initialize logging
3. announce startup

No other behavior is implemented.

## Boundary design

The repository already defines future subsystem namespaces:

- `core`
- `speech`
- `planner`
- `executor`
- `plugins`
- `memory`
- `ui`
- `llm`

These directories exist so future contributors can evolve the application deliberately instead of introducing cross-cutting behavior without structure.

## Why this matters

A desktop assistant with execution responsibilities needs:

- reliable bootstrap behavior
- explicit configuration
- strong observability
- testable boundaries
- room for dependency inversion

This release focuses on those prerequisites.
