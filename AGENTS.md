

\# ZÆNIA Development Instructions



\## Project

ZÆNIA is an offline-first personal AI assistant.



\## Source of truth

Read docs/architecture/ZAENIA\_Master\_Build\_Plan.md

before proposing architectural changes.



Inspect actual project files before modifying code.

Never assume earlier conversation details reflect current code.



\## Core architecture

1\. Reasoning and Planning Engine

2\. Learning and Memory Engine

3\. Execution and Security Engine



\## Security

\- Never commit secrets, credentials, or personal data.

\- Learning must never grant execution permissions.

\- Preserve authentication and authorization boundaries.

\- Obtain owner approval for sensitive operations.

\- Keep ZÆNIA functional without cloud services.



\## Development requirements

\- Explain code changes and their purpose.

\- Provide complete replacement files when requested.

\- Test modifications before claiming success.

\- Distinguish planned, implemented, and verified features.

\- Record relevant architectural decisions.

\- Update the master build plan when architecture changes.



\## Collaboration

ChatGPT and Claude must use the same repository history.

Develop changes on separate feature branches.

Do not overwrite another assistant's work without review.

Do not merge changes without owner approval.

## Latest handoff

Read docs/architecture/HANDOFF_2026-10-30.md first: it lists what Claude finished, how to build, test and install, and what is next.
