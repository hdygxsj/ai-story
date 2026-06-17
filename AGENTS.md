# Agent Instructions

When adding, removing, or changing any backend HTTP API route or Agent runtime tool, update the Go CLI command coverage, help text, and tests in the same change.

The Go CLI lives in `cli/`. Interface changes must keep `cli/internal/coverage`, command behavior, and relevant tests synchronized with the backend.
