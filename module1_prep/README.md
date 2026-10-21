# ZÆNIA Module 1 preparation

This package preserves Grey's approved moral-code specification and provides a source-only export utility. It does not install, replace or initialize authentication, and does not ask for a passkey.

Files:
- MORAL_CODE.md — the moral framework, context requirements, planned layout and completion criteria.
- moral_code.charter.json — the owner's original statement, clarifications and structured requirements.
- collect_module1_source.py — Python 3.11-compatible source export.
- README.md — these instructions.

## Export the current source

Extract this package into C:\Projects\ZAENIA\module1_prep, then run these commands in PowerShell:

    cd C:\Projects\ZAENIA
    py -3.11 .\module1_prep\collect_module1_source.py --project-root .

The utility creates ZAENIA_Module1_Source_Review.zip in the project root. Upload that generated archive to the build chat.

The export selects Python source from core/foundation and core/api, plus existing main.py, start.py, foundation_main.py and requirements.txt. It includes a Python-source path inventory so any additional dispatcher integration files can be identified.

It excludes data, .env files, configuration files, credentials, logs, recordings, model files and compiled bytecode. It redacts common hard-coded credential literals and comments in the exported copies; original files are unchanged. Redaction is a best-effort aid and cannot detect every possible secret embedded in arbitrary source. Review the generated archive before sharing if you have ever hard-coded a real credential in source.

Requirements: Windows with Python 3.11 already installed. Only Python's standard library is used. No paid services, new packages or network connection are needed.

## Next implementation step

The current foundation files are needed to preserve their interfaces, credentials and protected routes. The source archive will allow complete replacement files and the nested moral-code component to be built against the actual project.

The moral specification is complete. Runtime authentication, moral enforcement, full scripture import and end-to-end integration still require implementation and verification. Set or enter any owner passkey only in the local application.

