const AUTONOMOUS_SCORE_THRESHOLD = 70;
const DAILY_APPLICATION_LIMIT = 25;
const COMPANY_APPLICATION_LIMIT = 5;
const EXCLUDED_SENIORITY = /\b(senior|staff|lead|principal|manager|director|vice president|vp)\b/i;

function result(decision, reasons = []) {
  return { decision, reasons };
}

/**
 * Evaluates a job using Hunain's agreed application policy.
 * This function is intentionally deterministic so the dashboard can explain
 * every decision and persist the reason in the application ledger.
 */
export function decideApplication(job) {
  if (job.requiresAssessment) {
    return result("assessment_requested", ["Assessment requires human completion."]);
  }

  if (job.requiresExtendedLegalConsent) {
    return result("blocked", ["Application requires consent beyond ordinary application terms."]);
  }

  const rejectionReasons = [];
  if (Number(job.score) < AUTONOMOUS_SCORE_THRESHOLD) {
    rejectionReasons.push("Score is below the 70-point autonomous threshold.");
  }
  if (EXCLUDED_SENIORITY.test(job.title || "")) {
    rejectionReasons.push("Role title indicates excluded seniority.");
  }
  if (job.isCanadaEligible === false) {
    rejectionReasons.push("Role is not eligible for a Canada-based applicant.");
  }
  if (job.requiresCitizenship) {
    rejectionReasons.push("Role requires citizenship or permanent residence.");
  }
  if (job.requiresSecurityClearance) {
    rejectionReasons.push("Role requires security clearance.");
  }
  if (job.requiresProvincialLicence) {
    rejectionReasons.push("Role requires a provincial licence.");
  }

  if (rejectionReasons.length > 0) {
    return result("rejected", rejectionReasons);
  }

  if (Number(job.applicationsToday) >= DAILY_APPLICATION_LIMIT) {
    return result("deferred", ["Daily application limit has been reached."]);
  }
  if (Number(job.companyApplicationCount) >= COMPANY_APPLICATION_LIMIT) {
    return result("deferred", ["Company application limit has been reached."]);
  }

  return result("ready_to_apply");
}

/** Returns the expected annual base salary in CAD. */
export function salaryExpectation(range) {
  if (!range || !Number.isFinite(range.min) || !Number.isFinite(range.max)) {
    return 75000;
  }

  if (range.min >= 90000) return range.min;
  if (range.max < 70000) return range.max;
  if (range.min <= 90000 && range.max >= 70000) return 75000;

  return 75000;
}

/**
 * Prefer highest-score roles and remove near-duplicates by normalized title.
 * At most five distinct roles at a company enter the application queue.
 */
export function selectCompanyApplications(jobs) {
  const selectedTitles = new Set();
  return [...jobs]
    .sort((a, b) => Number(b.score) - Number(a.score))
    .filter((job) => {
      const title = (job.title || "").trim().toLowerCase().replace(/\s+/g, " ");
      if (selectedTitles.has(title)) return false;
      selectedTitles.add(title);
      return true;
    })
    .slice(0, COMPANY_APPLICATION_LIMIT);
}

export const applicationPolicy = {
  autonomousScoreThreshold: AUTONOMOUS_SCORE_THRESHOLD,
  dailyApplicationLimit: DAILY_APPLICATION_LIMIT,
  companyApplicationLimit: COMPANY_APPLICATION_LIMIT,
};

/** Maps a scored job and decision into the immutable application ledger shape. */
export function ledgerRecord(job, policyDecision) {
  return {
    job_id: job.id,
    company_name: job.company_name,
    job_title: job.title,
    apply_url: job.apply_url,
    source_url: job.source_url || null,
    match_score: Number(job.score),
    status: policyDecision.decision,
    policy_reasons: policyDecision.reasons,
    next_action: policyDecision.decision === "ready_to_apply"
      ? "Autonomous application pending"
      : null,
  };
}
