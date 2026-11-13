# Potemkin Remediation Playbook

Use these verified patterns when fixing findings reported by `scripts/potemkin.py`. Never bypass findings with dummy workarounds or disabled tests.

---

## 1. Replace Hollow UI (`POT001`–`POT003`)

**Before (Potemkin):**
```tsx
<button onClick={() => alert('Exporting PDF summary...')}>Download Report</button>
```

**After (Real Action):**
```tsx
<button onClick={handleDownloadReport} disabled={isDownloading}>
  {isDownloading ? 'Exporting...' : 'Download Report'}
</button>
```

If a feature is genuinely deferred for a future milestone, **remove the unimplemented button/tab** rather than shipping a clickable fake control.

---

## 2. Eliminate Deceptive Fallbacks (`POT004`–`POT005`)

**Before (Potemkin):**
```ts
try {
  const patients = await db.patient.findMany();
  return NextResponse.json(patients);
} catch {
  return NextResponse.json(MOCK_PATIENTS);
}
```

**After (Real Error Handling):**
```ts
try {
  const patients = await db.patient.findMany({ take: 50 });
  return NextResponse.json(patients);
} catch (err) {
  logger.error({ err }, 'failed_to_list_patients');
  return NextResponse.json({ error: 'Unable to fetch patients' }, { status: 500 });
}
```

---

## 3. Verify Webhook Signatures (`POT006`)

**Before (Potemkin):**
```ts
export async function POST(req: Request) {
  const body = await req.json();
  await handleBillingEvent(body);
  return NextResponse.json({ received: true });
}
```

**After (Cryptographic Verification):**
```ts
import crypto from 'node:crypto';

export async function POST(req: Request) {
  const rawBody = await req.text();
  const signature = req.headers.get('x-webhook-signature') ?? '';
  const secret = process.env.WEBHOOK_SECRET;
  if (!secret) throw new Error('WEBHOOK_SECRET is required');

  const expected = crypto.createHmac('sha256', secret).update(rawBody).digest('hex');
  const sigBuf = Buffer.from(signature, 'utf8');
  const expBuf = Buffer.from(expected, 'utf8');
  if (sigBuf.length !== expBuf.length || !crypto.timingSafeEqual(sigBuf, expBuf)) {
    return NextResponse.json({ error: 'Invalid signature' }, { status: 401 });
  }
  await handleBillingEvent(JSON.parse(rawBody));
  return NextResponse.json({ received: true });
}
```

---

## 4. Fail Fast on Missing Secrets & Clean Client Prefixes (`POT011`–`POT013`)

**Before (Potemkin):**
```ts
const secret = process.env.JWT_SECRET || 'dev-secret-change-me';
```

**After (Validated Env):**
```ts
function requireEnv(name: string): string {
  const val = process.env[name];
  if (!val) throw new Error(`Missing required environment variable: ${name}`);
  return val;
}
const secret = requireEnv('JWT_SECRET');
```

And never expose secrets with `NEXT_PUBLIC_`, `VITE_`, or `EXPO_PUBLIC_` — fetch privileged operations through authenticated server routes or Server Actions.

---

## 5. Restore Honest Verification (`POT014`–`POT016`)

If a test fails after a change:
1. Check whether your new code introduced a regression or schema incompatibility.
2. Fix the implementation bug (or update expectations only when the specification genuinely changed, preserving full assertions).
3. Never commit `it.skip`, `pytest.mark.skip`, `@ts-ignore`, `# type: ignore`, or `--no-verify` just to force exit code `0`.
