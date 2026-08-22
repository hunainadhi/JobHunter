# JobHunter Application Workflow

This adds an application ledger to the existing JobHunter dashboard. It prepares and tracks applications. It does not store a candidate's address, work-permit details, or voluntary self-identification data in this repository.

## What is implemented

- A deterministic policy engine for the agreed application rules.
- A Queue button next to each matched job.
- An Application Ledger page at `/applications`.
- A private Supabase ledger with submitted responses, materials, terms evidence, confirmation evidence, and next actions.
- A status lifecycle: discovered, scored, ready to apply, submitted, confirmation uncertain, assessment requested, interviewing, rejected, offer, withdrawn, blocked, and deferred.
- Server-side writes using `SUPABASE_SERVICE_KEY`. No anonymous policies are added for application data.

## Apply the migration

Apply `supabase/migrations/016_application_ledger.sql` to the same Supabase project that JobHunter already uses. This is the only database change required for the ledger.

The project does not currently have Supabase CLI credentials in this environment, so the migration has not been applied automatically.

## Configure the dashboard

The app accepts either the current Supabase variable names already in `app/.env.local`:

```dotenv
SUPABASE_URL=https://YOUR_PROJECT.supabase.co
SUPABASE_PUBLISHABLE_KEY=YOUR_PUBLISHABLE_KEY
SUPABASE_SECRET_KEY=YOUR_SERVER_ONLY_SECRET_KEY
```

or the legacy aliases:

```dotenv
NEXT_PUBLIC_SUPABASE_URL=https://YOUR_PROJECT.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=YOUR_ANON_KEY
SUPABASE_SERVICE_KEY=YOUR_SERVICE_ROLE_KEY
```

Never expose `SUPABASE_SERVICE_KEY` in client-side code or commit it to Git.

## Policy enforced by the queue

- Queue only jobs scoring at least 70.
- Exclude Senior, Staff, Lead, Principal, Manager, Director, and VP roles.
- Limit the day to 25 applications and a company to 5 distinct applications.
- Stop for assessments and for obligations beyond ordinary application terms.
- Use CAD 75,000 by default for an application that requires salary expectations but has no range.

The current schema records a job after it is queued. A browser automation worker can later update that row to `submitted`, attach the exact field values and materials, save a confirmation ID or screenshot link, and set a next action.

## External submission worker

Live applications are not yet connected to this dashboard. That requires an authenticated browser session for each applicant-tracking system and portal-specific handling for fields, captchas, and confirmation pages. It should use a protected candidate profile outside this repository and write only the final audit record into `application_ledger`.

Do not let a worker submit an assessment, a recorded interview, a take-home, or any form that creates obligations beyond a normal application.

## Verify locally

```bash
cd app
npm test
npm run lint
NEXT_PUBLIC_SUPABASE_URL=https://example.supabase.co \
NEXT_PUBLIC_SUPABASE_ANON_KEY=dummy \
SUPABASE_SERVICE_KEY=dummy \
npm run build
```
