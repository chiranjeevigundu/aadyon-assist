// Shared dark theme — mirrors the dashboard's "life-ops console" look.
export const theme = {
  bg: "#0b0f17",
  card: "#141b27",
  cardAlt: "#1b2433",
  border: "#243044",
  text: "#e6edf6",
  textDim: "#8a98ac",
  accent: "#5b9cff",
  // Honest score bands — green good, amber watch, red fire.
  good: "#3fb27f",
  watch: "#e0a64b",
  bad: "#e55b6a",
};

// Map a 0–100 score (or a band string) to a colour.
export function scoreColor(score: number): string {
  if (score >= 67) return theme.good;
  if (score >= 34) return theme.watch;
  return theme.bad;
}

export function bandColor(band?: string): string {
  switch ((band || "").toLowerCase()) {
    case "good":
    case "strong":
    case "healthy":
      return theme.good;
    case "watch":
    case "fair":
    case "ok":
      return theme.watch;
    default:
      return theme.bad;
  }
}
