# Source attribution and licensing

## Original-language data

Credit: **STEP Bible**, https://www.STEPBible.org/, based on work at **Tyndale House Cambridge**, https://www.TyndaleHouse.com/.

Source: https://github.com/STEPBible/STEPBible-Data/tree/master/Translators%20Amalgamated%20OT%2BNT

License: **Creative Commons Attribution 4.0 International**, https://creativecommons.org/licenses/by/4.0/. The legal text is included at `data/scripture/CC-BY-4.0.txt`; the publisher README is included beside it.

Datasets: TAHOT (Translators Amalgamated Hebrew OT), four source files, and TAGNT (Translators Amalgamated Greek NT), two source files. TAHOT provides Hebrew/Aramaic word data with morphological and semantic fields and textual variants. TAGNT provides amalgamated Greek records with edition/witness distinctions, morphology and context-sensitive English glosses. Edition/variant labels must not be discarded when displaying the records.

Adaptation: Source TSV word rows were converted into JSON field arrays and indexed in a SQLite database. All word fields and raw references are retained; redundant verse-level display rows were not duplicated. No correction to the source word text or gloss fields is asserted. The full source headers remain in the database metadata. The immutable source commit, download URLs and SHA-256 hashes are recorded in `corpus_manifest.json`.

This is a derived offline application corpus, not an official STEP Bible product or a claim of endorsement. Source updates or corrections should be checked against the publisher repository; this release is a named snapshot.

## English comparisons

**American Standard Version (1901)**, eBible.org: https://ebible.org/details.php?id=eng-asv

**World English Bible Classic**, eBible.org: https://ebible.org/details.php?id=eng-web

Both English sources are public domain. “World English Bible” is the publisher's trademark. The included VPL verse text is stored unchanged. Publisher notices are included as `eng-asv_about.htm` and `eng-web_about.htm`.

The declared corpus contains 66 books. WEB's additional deuterocanonical/apocryphal source rows were omitted explicitly from this collection, with book counts recorded in the manifest. No original-language coverage for those additional books is claimed.

## Software

Dependency packages are installed from their distributions with their own license metadata. They are not vendored inside this ZIP. All direct module dependencies are free/open-source; exact checked versions are in `requirements-module1.txt`.

Primary implementation references:

- Argon2-cffi: https://argon2-cffi.readthedocs.io/en/stable/api.html
- Cryptography Fernet: https://cryptography.io/en/latest/fernet/
- Microsoft security descriptors: https://learn.microsoft.com/en-us/windows/win32/api/sddl/nf-sddl-convertstringsecuritydescriptortosecuritydescriptorw
- Microsoft DACL application: https://learn.microsoft.com/en-us/windows/win32/api/aclapi/nf-aclapi-setnamedsecurityinfow
