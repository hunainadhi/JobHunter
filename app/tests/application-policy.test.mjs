import test from "node:test";
import assert from "node:assert/strict";
import {
  decideApplication,
  salaryExpectation,
  selectCompanyApplications,
  ledgerRecord,
} from "../lib/application-policy.mjs";

const eligibleJob = {
  score: 82,
  title: "Software Engineer",
  location: "Toronto, Ontario, Canada",
  companyApplicationCount: 0,
  applicationsToday: 3,
};

test("approves a high-fit Canadian early-career role", () => {
  const result = decideApplication(eligibleJob);

  assert.deepEqual(result, { decision: "ready_to_apply", reasons: [] });
});

test("rejects roles below the autonomous score threshold", () => {
  const result = decideApplication({ ...eligibleJob, score: 69 });

  assert.equal(result.decision, "rejected");
  assert.deepEqual(result.reasons, ["Score is below the 70-point autonomous threshold."]);
});

test("rejects seniority and eligibility blockers before applying", () => {
  const result = decideApplication({
    ...eligibleJob,
    title: "Senior Backend Engineer",
    requiresCitizenship: true,
  });

  assert.equal(result.decision, "rejected");
  assert.deepEqual(result.reasons, [
    "Role title indicates excluded seniority.",
    "Role requires citizenship or permanent residence.",
  ]);
});

test("blocks assessment work while leaving the ordinary application ready", () => {
  const result = decideApplication({ ...eligibleJob, requiresAssessment: true });

  assert.deepEqual(result, {
    decision: "assessment_requested",
    reasons: ["Assessment requires human completion."],
  });
});

test("skips an application that requires an unsupported legal obligation", () => {
  const result = decideApplication({ ...eligibleJob, requiresExtendedLegalConsent: true });

  assert.deepEqual(result, {
    decision: "blocked",
    reasons: ["Application requires consent beyond ordinary application terms."],
  });
});

test("enforces daily and per-company application limits", () => {
  const daily = decideApplication({ ...eligibleJob, applicationsToday: 25 });
  const company = decideApplication({ ...eligibleJob, companyApplicationCount: 5 });

  assert.deepEqual(daily, {
    decision: "deferred",
    reasons: ["Daily application limit has been reached."],
  });
  assert.deepEqual(company, {
    decision: "deferred",
    reasons: ["Company application limit has been reached."],
  });
});

test("uses the approved salary rules", () => {
  assert.equal(salaryExpectation({ min: 100000, max: 120000 }), 100000);
  assert.equal(salaryExpectation({ min: 80000, max: 110000 }), 75000);
  assert.equal(salaryExpectation({ min: 55000, max: 65000 }), 65000);
  assert.equal(salaryExpectation(null), 75000);
});

test("keeps only the strongest distinct jobs per company", () => {
  const selected = selectCompanyApplications([
    { id: "1", title: "Software Engineer", score: 92 },
    { id: "2", title: "Software Engineer", score: 89 },
    { id: "3", title: "Backend Engineer", score: 85 },
    { id: "4", title: "AI Engineer", score: 80 },
  ]);

  assert.deepEqual(selected.map((job) => job.id), ["1", "3", "4"]);
});

test("creates an auditable ledger record from a policy decision", () => {
  const record = ledgerRecord({
    id: "job-1",
    title: "Software Engineer",
    company_name: "Acme",
    apply_url: "https://jobs.example.com/1",
    source_url: "https://source.example.com/1",
    score: 82,
  }, { decision: "ready_to_apply", reasons: [] });

  assert.deepEqual(record, {
    job_id: "job-1",
    company_name: "Acme",
    job_title: "Software Engineer",
    apply_url: "https://jobs.example.com/1",
    source_url: "https://source.example.com/1",
    match_score: 82,
    status: "ready_to_apply",
    policy_reasons: [],
    next_action: "Autonomous application pending",
  });
});
