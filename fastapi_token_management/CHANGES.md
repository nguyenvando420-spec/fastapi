# Changes from Enterprise-grade Upgrade

This file documents all the major enterprise features added to the FastAPI Token Management project.

## 1. Security & Core Upgrades
- Added **Refresh Token** flow (`POST /api/v1/auth/refresh`).
- Added **Token Blacklist (Logout)** via `RevokedToken` model (`POST /api/v1/auth/logout`) and prevented blacklisted tokens via `api/dependencies.py`.
- Added **CORS Middleware** configuration.
- Added **Global Exception Handler** with graceful JSON responses.
- Added `X-Request-ID` and `X-Process-Time` middleware for tracing.
- Upgraded `/health` check with memory, db connection status, and environment settings.
- Added `validate_password_strength` rule (enforced complexity).

## 2. Admin Module Upgrades
- Added `is_active` (soft delete flag) to both `System` and `Domain` models.
- Added Regex Validator for SQL Safety guaranteeing schema names only use [a-z0-9_].
- Exposed generic GET list with advanced pagination schema: `PaginatedResponse`.
- Added FULL CRUD APIs:
  - `GET /api/v1/admin/systems`
  - `GET /api/v1/admin/systems/{id}`
  - `DELETE /api/v1/admin/systems/{id}`
  - `GET /api/v1/admin/domains`
  - `GET /api/v1/admin/domains/{id}`
  - `DELETE /api/v1/admin/domains/{id}`

## 3. Audit Module Upgrades
- Enhanced `AuditLog` fields: Added `request_id`, `ip_address`, `http_method`, and `path`.
- Enhanced `GET /api/v1/audit/` endpoint to accept `from_date` and `to_date` filters.
- Added pagination totals returned properly format `{total, limit, offset, items}`.
- Developed Dashboard API: `GET /api/v1/audit/stats` displaying analytics (Top Users, HTTP stats, total requests).

## 4. Token Module Upgrades
- Added a `MAX_BATCH_SIZE` of 1000 validation rule to `TokenizeRequest`/`DeTokenizeRequest`.
- Improved De-Tokenize Response to export `missing_tokens: []` array, separating failed decryptions from purely missing entries in DB.
- Developed Statistics Table: `GET /api/v1/tokens/stats` querying raw dataset row count inside dynamic polymorphic Token tables.

## 5. Auth / User Upgrades
- Added `GET /api/v1/auth/me` endpoint to retrieve user profile data.
