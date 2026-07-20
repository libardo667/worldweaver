# Signed resident lifecycle proof

Date: 2026-07-20  
City: local Alderbank backend (`ww_alderbank`)  
Participant: disposable synthetic actor `synthetic-reference-proof`

## Question

Can a resident use its own admitted identity, rather than a shared shard secret, to open a city session, read
a protected current scene, and leave cleanly through the real running backend?

## Method

The proof created a disposable hearth in `/tmp`, generated a public resident identity card and a private key
sealed for Alderbank's hearth host, and admitted only the public card through the city operator command. A
resident-specific `WorldWeaverClient` then:

1. discovered Alderbank's public shard ID;
2. opened the sealed long-term identity key only to sign a one-hour runtime key;
3. completed signed session bootstrap;
4. requested the protected current scene; and
5. sent signed leave and checked the actor's remaining city sessions.

The repeated final run returned this content-free structural result:

```json
{
  "bootstrap_state": "completed",
  "bootstrap_success": true,
  "cleanup_fields": ["sessions"],
  "leave_success": true,
  "scene_available": true,
  "signed_client": true
}
```

The city authority record showed runtime generation 1 and no remaining bound sessions after leave.

## Privacy boundary

No model ran. The test did not create, read, or print a private ledger, prompt, completion, resident thought,
or existing resident file. It checked only identity metadata and structural HTTP results.

## What this proves

- Alderbank accepts an explicitly admitted resident public identity.
- The hearth host can issue a short-lived actor- and generation-bound runtime key without placing the
  long-term private key in a plaintext file.
- Ordinary protected requests can use that runtime key.
- Signed leave removes the disposable actor's public city session.

## What this does not prove

- No model-driven resident choice was exercised.
- Both client and city ran on one physical computer over local HTTP.
- Inter-city travel, off-device hosting, recovery, revocation, and malicious-host resistance were not tested.
- The synthetic public authority row remains as labeled test evidence, with no session attached. There is not
  yet an operator revocation command for that row.

The next proof is a newly created resident with an empty private ledger using the small reference loop. Their
name, model, run length, public admission, and privacy boundary should be chosen before creation and waking.
