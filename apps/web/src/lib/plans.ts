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

// Returns true if the user's plan is at or above the required plan level.
export function planAtLeast(userPlan: PlanName, required: PlanName): boolean {
  return PLAN_ORDER.indexOf(userPlan) >= PLAN_ORDER.indexOf(required);
}
