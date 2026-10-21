# ADR 001 foroba ui local dep

# ADR-001: @foroba/ui as local file dependency

**Status**: Accepted  
**Date**: 2026-06-15

## Context
@foroba/ui has not yet been published to the GitLab Package Registry via CI (requires a CI runner with access). We need it available immediately.

## Decision
Use `"@foroba/ui": "file:../foroba-ui"` in `package.json` pointing to the sibling directory on disk.

## Consequences
- Works immediately without CI. Local pnpm resolves the symlink.
- When CI publishes `@foroba/ui@0.1.0` to the registry, replace with `"@foroba/ui": "^0.1.0"` and update `.npmrc`.

