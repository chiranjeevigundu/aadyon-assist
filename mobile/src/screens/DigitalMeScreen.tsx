import React, { useCallback, useEffect, useState } from "react";
import { View, Text, StyleSheet } from "react-native";
import { Screen, Card, ScoreBadge, Pill, Loading, ErrorBox, Row } from "../components";
import { api, DigitalMe } from "../api";
import { theme, scoreColor, bandColor } from "../theme";

const DIM_LABELS: Record<string, string> = {
  financial: "Financial",
  visa: "Visa / Status",
  career: "Career",
  goal: "Goal · by 30",
};

export default function DigitalMeScreen() {
  const [data, setData] = useState<DigitalMe | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    try {
      setErr(null);
      const d = await api.digitalMe();
      setData(d);
    } catch (e: any) {
      setErr(e?.message || String(e));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) return <Loading label="Loading Digital Me…" />;
  if (err && !data) return <Screen onRefresh={() => { setRefreshing(true); load(); }} refreshing={refreshing}><ErrorBox message={err} /></Screen>;

  const p = data!.profile || {};
  const life = data!.life || {};
  const dims = data!.dimensions || {};
  const overall = data!.overall || { score: 0 };

  return (
    <Screen onRefresh={() => { setRefreshing(true); load(); }} refreshing={refreshing}>
      {/* Identity + overall */}
      <Card>
        <View style={s.headerRow}>
          <View style={{ flex: 1 }}>
            <Text style={s.name}>{p.preferred_name || p.full_name || "You"}</Text>
            {p.headline ? <Text style={s.headline}>{p.headline}</Text> : null}
            <Text style={s.sub}>
              {[p.location, p.visa_type, p.visa_status].filter(Boolean).join(" · ")}
            </Text>
          </View>
          <View style={{ alignItems: "center", gap: 6 }}>
            <ScoreBadge score={overall.score} size={72} />
            <Pill text={(overall.band || bandLabel(overall.score)).toUpperCase()} color={scoreColor(overall.score)} />
          </View>
        </View>
      </Card>

      {/* Life track */}
      {Object.keys(life).length ? (
        <Card title="Life so far">
          <Row label="Days alive" value={fmt(life.days_alive)} />
          <Row label="Life lived" value={pct(life.life_lived_pct)} />
          <Row label="Age" value={life.age} />
          <Row label="Days to 30" value={fmt(life.days_to_30 ?? life.days_to_goal)} />
        </Card>
      ) : null}

      {/* Dimensions */}
      <Text style={s.section}>Dimensions</Text>
      {Object.entries(dims).map(([key, dim]) => (
        <DimensionCard key={key} name={DIM_LABELS[key] || key} dim={dim} />
      ))}

      <Text style={s.asOf}>as of {data!.as_of}</Text>
    </Screen>
  );
}

function DimensionCard({ name, dim }: { name: string; dim: any }) {
  const score = dim?.score ?? 0;
  const band = dim?.band || bandLabel(score);
  const comps: Record<string, any> = dim?.components || {};
  return (
    <Card>
      <View style={s.dimHead}>
        <ScoreBadge score={score} size={52} />
        <View style={{ flex: 1, marginLeft: 14 }}>
          <Text style={s.dimName}>{name}</Text>
          <Pill text={band.toUpperCase()} color={bandColor(band)} />
        </View>
      </View>
      {Object.entries(comps).length ? (
        <View style={s.compBox}>
          {Object.entries(comps).map(([k, v]) => (
            <Row key={k} label={prettify(k)} value={formatComp(v)} dim />
          ))}
        </View>
      ) : null}
    </Card>
  );
}

// ---- helpers ----
function bandLabel(score: number) {
  if (score >= 67) return "good";
  if (score >= 34) return "watch";
  return "fire";
}
function fmt(n: any) {
  if (n === null || n === undefined) return undefined;
  const x = Number(n);
  return isNaN(x) ? n : x.toLocaleString();
}
function pct(n: any) {
  if (n === null || n === undefined) return undefined;
  const x = Number(n);
  return isNaN(x) ? n : `${x.toFixed(1)}%`;
}
function prettify(k: string) {
  return k.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}
function formatComp(v: any) {
  if (typeof v === "number") return Number.isInteger(v) ? v.toLocaleString() : v.toFixed(2);
  if (typeof v === "boolean") return v ? "yes" : "no";
  if (v && typeof v === "object") return JSON.stringify(v);
  return v;
}

const s = StyleSheet.create({
  headerRow: { flexDirection: "row", alignItems: "center", gap: 12 },
  name: { color: theme.text, fontSize: 22, fontWeight: "800" },
  headline: { color: theme.accent, fontSize: 14, marginTop: 2 },
  sub: { color: theme.textDim, fontSize: 13, marginTop: 6 },
  section: { color: theme.textDim, fontSize: 12, fontWeight: "700", letterSpacing: 1, textTransform: "uppercase", marginBottom: 10, marginTop: 4 },
  dimHead: { flexDirection: "row", alignItems: "center" },
  dimName: { color: theme.text, fontSize: 16, fontWeight: "700", marginBottom: 6 },
  compBox: { marginTop: 12, borderTopWidth: 1, borderTopColor: theme.border, paddingTop: 6 },
  asOf: { color: theme.textDim, fontSize: 11, textAlign: "center", marginTop: 4 },
});
