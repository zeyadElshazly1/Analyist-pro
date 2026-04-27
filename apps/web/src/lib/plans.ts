export const PLAN_NAMES = {
  FREE:       "free",
  CONSULTANT: "consultant",
  STUDIO:     "studio",
} as const;

export type PlanName = (typeof PLAN_NAMES)[keyof typeof PLAN_NAMES];

export const PLAN_LABELS: Record<PlanName, string> = {
  [PLAN_NAMES.FREE]:       "Free",
  [PLAN_NAMES.CONSULTANT]: "Consultant",
  [PLAN_NAMES.STUDIO]:     "Studio",
};

export const PLAN_ORDER: PlanName[] = [
  PLAN_NAMES.FREE,
  PLAN_NAMES.CONSULTANT,
  PLAN_NAMES.STUDIO,
];

// Per-plan upload size cap in MB. Mirrors apps/api/app/middleware/plans.py
// (PLAN_LIMITS.max_file_mb). Keep these in sync.
export const PLAN_FILE_LIMITS_MB: Record<PlanName, number> = {
  [PLAN_NAMES.FREE]:       10,
  [PLAN_NAMES.CONSULTANT]: 100,
  [PLAN_NAMES.STUDIO]:     500,
};

const LEGACY_PLAN_MAP: Record<string, PlanName> = {
  pro:  PLAN_NAMES.CONSULTANT,
  team: PLAN_NAMES.STUDIO,
};

/**
 * Map any plan-like value (canonical, legacy, undefined, or unknown) to a
 * canonical PlanName. Legacy "pro"/"team" map to consultant/studio; anything
 * else (null, "", "enterprise", "Pro" with capitals, etc.) falls back to
 * "free" so downstream gates never crash on dirty data.
 */
export function normalizePlan(plan: string | null | undefined): PlanName {
  if (!plan) return PLAN_NAMES.FREE;
  const lower = plan.toLowerCase();
  const mapped = (LEGACY_PLAN_MAP[lower] ?? lower) as PlanName;
  return (PLAN_ORDER as string[]).includes(mapped) ? mapped : PLAN_NAMES.FREE;
}

/**
 * True if the user's plan is at or above the required plan level. Both inputs
 * are normalised first, so legacy values ("pro"/"team") and unknown plans
 * never throw.
 */
export function planAtLeast(
  userPlan: string | null | undefined,
  required: string | null | undefined,
): boolean {
  return PLAN_ORDER.indexOf(normalizePlan(userPlan)) >= PLAN_ORDER.indexOf(normalizePlan(required));
}

/**
 * Human-readable upload-size hint for an upload UI. Returns a generic message
 * when the plan is unknown so the UI never lies about a specific limit it
 * cannot enforce.
 */
export function uploadHintForPlan(plan: string | null | undefined): string {
  if (!plan) return "File size limit depends on your plan.";
  const canonical = normalizePlan(plan);
  return `Max ${PLAN_FILE_LIMITS_MB[canonical]} MB`;
}
