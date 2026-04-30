/**
 * Sample column snippets for CategoricalMiniViz in Column Profiles.
 * Use for manual QA or future tests: tooltips should show fullLabel, not bar index.
 */
type TopValues = Record<string, number>;

export const FIXTURE_PROFILE_GENDER = {
  column: "gender",
  type: "categorical" as const,
  top_values: { Female: 5032, Male: 4821 } satisfies TopValues,
};

export const FIXTURE_PROFILE_CHURN = {
  column: "Churn",
  type: "categorical" as const,
  top_values: { Yes: 1869, No: 5174 } satisfies TopValues,
};

export const FIXTURE_PROFILE_SENIOR_BINARY = {
  column: "SeniorCitizen",
  type: "numeric" as const,
  is_binary: true as const,
  value_label_map: { "0": "Not senior", "1": "Senior" } as Record<string, string>,
  top_values: { "0": 5901, "1": 1142 } satisfies TopValues,
};

export const FIXTURE_PROFILE_PARTNER = {
  column: "Partner",
  type: "categorical" as const,
  top_values: { Yes: 3641, No: 3402 } satisfies TopValues,
};
