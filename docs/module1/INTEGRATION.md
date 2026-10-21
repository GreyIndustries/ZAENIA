# Foundation integration contract

## Trust boundary

The model proposes `ActionRequest(operation, params)`. It receives no passphrase, fresh-auth object, session, grant factory, arbitrary callable, module import or shell execution interface. Operation names come from the fixed catalog in `rules/models.py`. A name alone does not create a handler or permission.

Trusted startup code authenticates locally, opens `RuleEngine`, registers each actual operation with a trusted callable and a resource validator, and seals registration. A validator must reject unknown fields, canonicalize resource identifiers, enforce permitted directories/accounts and resource limits, and return a plain JSON-compatible parameter dictionary. File tools must reject secure storage, project/security code and reparse/link escapes where a model could otherwise rewrite the policy implementing the gate.

`prepare()` produces the parameters to display to the owner. `execute()` validates again, checks the active owner session, verifies protected policy, applies enabled scope rules, evaluates the moral assessment and consumes required proofs immediately before calling the registered handler. `evaluate()` and the legacy `check` command are diagnostics; their results do not grant execution authority.

## Owner interaction

For sensitive operations, the trusted owner interaction layer calls `session.reauthenticate(operation, canonical_params)` after showing the exact proposed action. That local call requests the owner passphrase and returns a one-use grant. Never turn the grant-creation method into a model tool or HTTP client endpoint. Changed parameters, another session, forgery, expiry, logout and replay invalidate authorization.

Permanent file deletion also needs two actual owner choices. After the first choice, call `confirm_after_owner_choice(operation, params)`. After the separate second choice, call it with `previous=first_proof`. Only the second returned proof can be consumed, and only once for the same action and parameters. Calling these methods automatically without owner choices violates this contract.

For contextual/consequential moral cases, display the facts, evidence/source limits, relational context and proposed response. Owner review is bound as:

```text
operation: moral.review
params:
  request:
    operation: the registered action
    params: its canonical parameters
  case: dataclasses.asdict(the reviewed MoralCase)
```

Use a fresh grant from `session.reauthenticate("moral.review", binding)`. Pass it as `moral_review` with the unchanged case to `execute()`. A planner cannot grant review by setting `facts_confirmed=true`. Review cannot override a prohibited method. `ALLOW`, `BLOCK` and `ASK_FOR_CONTEXT` describe the moral assessment, not identity authentication.

## Scripture and model context

`Corpus.passage(reference, passphrase=...)` returns original words and transliterations, glosses, morphology/lexical fields, all source fields including editions/variants, translation comparisons, three surrounding chapters and explicit missing context fields. Context notes are separate sourced interpretations, not additions to the biblical text. Original-reference alternate numbering must remain visible when comparing witnesses/translations.

`guidance_for_generation()` exposes only the protected compass, not credentials or private owner notes. The supplied chat route attaches it to generation input while retaining `execution_authorized=false`. When implementing the brain's structured system/context interface, place it in the trusted context role and retrieve relevant `Corpus` evidence there. Never treat this prompt text as the enforcement mechanism for executing actions. Model prose still needs review and can be wrong.

The offline corpus allows all included passages to be retrieved; a search result or selected anchor is not a declaration that every passage relevant to God's love has been considered. Maintain the user's requirement to consider passage context, time, situation, culture and people. If those fields are missing, disclose that and obtain sourced review before asserting a doctrinal conclusion. Do not suppress ordinary protective guidance because scholarly metadata is absent.

## API service

`ScopedClientGate` requires fresh local owner startup approval for its fixed capabilities. Existing token hashing is compatible. Every protected request verifies the current token, then checks the applicable scoped capability and policy snapshot. There is no API passphrase login, owner session creation or grant minting. If encrypted policy or the primary credential changes, restart and authenticate the service.

CarPlay/brain service code is trusted application integration. The route-level checks do not authorize hidden nested writes inside a handler. Such operations must also use the typed dispatcher with their own validators and appropriate owner grants. The isolated HTTP tests substitute missing CarPlay services only to verify that unauthorized requests never initialize/call them; they do not simulate real calendar, Piper or microphone behavior.

## Existing encrypted data

The update preserves the existing Argon2 format and Scrypt/Fernet key derivation. Rules retain their master-key domain. Moral policy and Scripture context use distinct scoped domains. Existing speaker encryption remains compatible and its enrolled bytes are not rewritten. A missing or invalid master salt stops processing; it is never silently regenerated while encrypted vaults exist.

Hard rules and the exact moral charter are checked against the reviewed source baseline. Ordinary management edits are limited to soft rules, owner notes and sourced context. Principle changes require a reviewed versioned software change and fresh activation. Do not let prompt/persona learning modify policy files.

Primary passphrase rotation must account for every encrypted subsystem before implementation; this package provides API-token rotation and deliberately avoids a partial primary rotation that would strand speaker or other encrypted data.
