# Regulatory notes

> **Not legal advice.** This is a plain-language summary to help decide what to check with a lawyer. It reflects KaisenOS as currently designed: free, open-source software that each person runs on their own computer, where the author never receives anyone's data. **KaisenOS is not certified, audited, or "HIPAA-compliant", and makes no claim to be.** If the design changes (hosting, accounts, analytics, crash reporting, cloud sync, or selling the app), revisit everything below with a qualified attorney.

## Summary

| Law / rule | Likely applies as designed? | Why |
|---|---|---|
| **HIPAA** (US) | Generally **no** | HIPAA covers health plans, health-care clearinghouses, providers that bill electronically, and their business associates. An individual tracking their own fitness on their own computer isn't one, and the author doesn't receive or handle anyone's health information. A clinic or provider that adopted KaisenOS for patient data would have its own HIPAA obligations. |
| **FTC Act §5** (unfair or deceptive practices) | **Relevant if the app is promoted** | It prohibits misleading claims. The privacy and security docs here describe only what the code actually does, with no unsupported claims about encryption, anonymity or compliance. Keep it that way. |
| **FTC Health Breach Notification Rule** (16 CFR Part 318) | **Unclear; probably limited** | It covers vendors of personal health records and related entities. The FTC reads "health apps" broadly, including apps that draw data from several sources (for example, user input plus a wearable). The rule centers on breaches of data the vendor holds or controls. KaisenOS's author holds none. If the project ever collects, hosts or syncs user data, get legal advice. |
| **FDA** (medical devices) | Generally **no**, if claims stay general | FDA's *General Wellness* policy treats low-risk products for general fitness and wellness as outside active device regulation, as long as they don't claim to diagnose, treat, cure or prevent disease. KaisenOS avoids such claims and its coach is told not to diagnose. Adding disease-specific features or claims could change this. |
| **State consumer health privacy laws** (e.g. Washington *My Health My Data Act*, Nevada SB 370, Connecticut's health-data amendments) | Likely **minimal** as designed | These regulate entities that collect or share consumer health data. With no collection by the author, there's little to regulate. Any future telemetry, crash reports or cloud features could bring these into play. Washington's law in particular has a broad scope and a private right of action. |
| **General privacy laws** (CCPA/CPRA, GDPR, etc.) | Likely **minimal** as designed | These apply to businesses that process personal data. Local processing by the user, with nothing going to the author, generally isn't processing by the author. |
| **Garmin API terms** | **Yes, for each user** | Each user creates and uses their own Personal API key for their own data, under Garmin's terms (personal, non-commercial use). The project doesn't distribute anyone's Garmin data. |

## Legal obligations vs. voluntary practices

- **Probable legal obligations as designed:** accurate, non-misleading descriptions of privacy and security (FTC Act §5); following Garmin's API terms; open-source license compliance for dependencies.
- **Voluntary best practices implemented** (not required by any of the laws above for this design):
  - local-only storage outside the repo, with owner-only permissions
  - localhost binding and DNS-rebinding and CSRF protections
  - strict content security policy
  - export, restore and delete
  - automatic backups with retention
  - dependency auditing and repo secret scanning
  - a safety-focused AI prompt and a medical disclaimer

## Things that would change this analysis

- Hosting KaisenOS for others, or adding accounts or cloud sync
- Adding analytics, telemetry or crash reporting that sends data anywhere
- Selling the app or offering it commercially
- Integrations that share data with third parties
- Clinical, diagnostic or treatment claims or features
- Use by health-care providers for patient data
