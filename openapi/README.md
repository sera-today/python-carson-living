# Carson reservation OpenAPI

`carson-reservations.openapi.yaml` is an unofficial OpenAPI 3.1 description
derived from authorized live observations on 2026-09-10. It contains no real
credentials, account IDs, building IDs, amenity IDs, reservation IDs, or
personal response payloads.

## Explore

- Swagger Editor: open <https://editor.swagger.io/> and import the YAML file.
- Postman: Import → Files → select the YAML file.
- Redocly CLI:

  ```sh
  npx @redocly/cli lint --config openapi/redocly.yaml \
    openapi/carson-reservations.openapi.yaml
  npx @redocly/cli preview-docs --config openapi/redocly.yaml \
    openapi/carson-reservations.openapi.yaml
  ```

For authorized live requests, set the `Authorization` header to `JWT <token>`.
Do not put resident credentials or tokens into a public/shared explorer. Create
and cancel operations should remain confirmation-gated and must be reconciled
against the authoritative reservation list after execution.

Carson's canonical observed paths include trailing slashes. The Redocly config
therefore disables its style rule against trailing slashes and its ambiguity
warning for Carson's overlapping literal and templated routes.
