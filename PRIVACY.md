# WhisperStash Privacy Policy

Last updated: February 22, 2026

This Privacy Policy applies to:
- The WhisperStash CLI
- The WhisperStash Chrome extension ("WhisperStash Local Decrypt")

## Summary

WhisperStash is designed to run locally on your device. We do not operate a cloud backend for WhisperStash and we do not collect, sell, or share your personal data for advertising.

## What data WhisperStash handles

For core functionality, WhisperStash may process:
- Encrypted tokens (`ENC[...]`)
- Text you explicitly choose to encrypt/decrypt/unwrap
- Extension-to-local-daemon requests sent to `http://127.0.0.1:8765`

This processing is local to your device to provide the product's single purpose: encrypting/decrypting user-provided text.

## What data we collect

We do not collect or transmit user data to developer-controlled servers, including:
- Personally identifiable information
- Health information
- Financial/payment information
- Authentication credentials for online accounts
- Location data
- Web history
- User activity telemetry
- Website content for analytics or profiling

## Data sharing

We do not sell or transfer user data to advertisers, data brokers, or other third parties.

WhisperStash Chrome extension communicates only with the local WhisperStash daemon running on your own device (`127.0.0.1`). This is required to provide decryption/encryption features.

## Limited Use and permitted use

WhisperStash uses data only to deliver its user-facing encryption/decryption functionality.

All other transfers, uses, or sale of user data are prohibited by our practices, including:
- Personalized advertising
- Data brokerage/resale
- Creditworthiness or lending-related use

The use of information received from Google APIs (if any) will adhere to the Chrome Web Store User Data Policy, including the Limited Use requirements.

## Human access

We do not run a service that gives us routine human access to your data. We do not review your data unless you explicitly provide information to us (for example, in a GitHub issue you submit).

## Security

WhisperStash is local-first and uses passphrase-based encryption (AES-GCM with PBKDF2 key derivation) in the CLI/daemon implementation. Data sent between extension components and the local daemon is limited to localhost traffic on your own machine.

## Data retention

Because we do not collect your data on remote servers, we do not maintain a remote retention store for WhisperStash user content.

Any local files, local logs, or local key material are controlled by you on your device.

## Your choices and controls

You can:
- Uninstall the extension at any time
- Stop the local daemon at any time
- Delete local encrypted files and local key files at any time
- Avoid storing a default key and use interactive prompts instead

## Changes to this policy

If WhisperStash data practices materially change, this policy will be updated before or at release of those changes.

## Contact

For privacy questions, open an issue in this repository:
- https://github.com/HubDamian95/whisperstash/issues

