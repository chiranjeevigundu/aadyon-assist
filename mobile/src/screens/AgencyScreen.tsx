import React, { useCallback, useEffect, useState } from "react";
import { View, Text, StyleSheet } from "react-native";
import { Screen, Card, Pill, Loading, ErrorBox } from "../components";
import { api } from "../api";
import { theme } from "../theme";

// Read-only view of the agentic org. Approvals/runs stay on the web console,
// to keep the human-in-the-loop boundary explicit.
export default function AgencyScreen() {
  const [org, setOrg] = useState<any>(null);
  const [tasks, setTasks] = useState<any[]>([]);
  const [health, setHealth] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    try {
      setErr(null);
      const [o, t, h] = await Promise.all([
        api.agencyOrg(),
        api.agencyTasks().catch(() => []),
        api.agencyHealth().catch(() => null),
      ]);
      setOrg(o);
      setTasks(Array.isArray(t) ? t : []);
      setHealth(h);
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

  if (loading) return <Loading label="Loading the org…" />;
  const refresh = () => { setRefreshing(true); load(); };
  if (err && !org) return <Screen onRefresh={refresh} refreshing={refreshing}><ErrorBox message={err} /></Screen>;

  const ceo = org?.ceo;
  const teams = org?.teams || [];
  const pending = tasks.filter((t) => /await|approv|pending|blocked/i.test(t.status || ""));

  return (
    <Screen onRefresh={refresh} refreshing={refreshing}>
      {/* Model health */}
      {health ? (
        <Card title="Model routing">
          <View style={s.healthRow}>
            <Pill
              text={(health.status || "unknown").toUpperCase()}
              color={/ok|up|ready/i.test(health.status) ? theme.good : theme.bad}
            />
          </View>
          {(health.routes || []).map((r: any, i: number) => (
            <View key={i} style={s.routeRow}>
              <Text style={s.routeTier}>{r.tier}</Text>
              <Text style={s.routeModel} numberOfLines={1}>
                {r.provider}/{r.model_id}
              </Text>
              <Text style={[s.routeActive, { color: r.active ? theme.good : theme.textDim }]}>
                {r.active ? "on" : "off"}
              </Text>
            </View>
          ))}
        </Card>
      ) : null}

      {/* Org chart */}
      <Card title="The org">
        {ceo ? <Member a={ceo} role="CEO" /> : <Text style={s.dim}>No CEO configured.</Text>}
        {teams.map((node: any, i: number) => (
          <View key={i} style={s.team}>
            <Text style={s.teamName}>
              {node.team?.name} {node.team?.dimension ? `· ${node.team.dimension}` : ""}
            </Text>
            {node.lead ? <Member a={node.lead} role="Lead" indent /> : null}
            {(node.employees || []).map((e: any, j: number) => (
              <Member key={j} a={e} role="Employee" indent />
            ))}
          </View>
        ))}
      </Card>

      {/* Pending approvals (read-only signpost) */}
      <Card title={`Awaiting your approval (${pending.length})`}>
        {pending.length ? (
          pending.map((t, i) => (
            <View key={i} style={s.task}>
              <Text style={s.taskTitle} numberOfLines={2}>{t.title || t.description || "task"}</Text>
              <Pill text={(t.status || "").toUpperCase()} color={theme.watch} />
            </View>
          ))
        ) : (
          <Text style={s.dim}>Nothing waiting. Approve/reject actions on the web console.</Text>
        )}
        <Text style={s.note}>
          Money, email, and filings never auto-execute — approve them yourself on /agency.
        </Text>
      </Card>
    </Screen>
  );
}

function Member({ a, role, indent }: { a: any; role: string; indent?: boolean }) {
  return (
    <View style={[s.member, indent && { marginLeft: 14 }]}>
      <View style={{ flex: 1 }}>
        <Text style={s.memberName}>{a.name}</Text>
        <Text style={s.memberTitle} numberOfLines={1}>{a.title || role}</Text>
      </View>
      {a.model_tier ? <Pill text={a.model_tier} color={theme.accent} /> : null}
    </View>
  );
}

const s = StyleSheet.create({
  healthRow: { flexDirection: "row", marginBottom: 10 },
  routeRow: { flexDirection: "row", alignItems: "center", paddingVertical: 5, gap: 10 },
  routeTier: { color: theme.text, fontWeight: "700", width: 78, fontSize: 13 },
  routeModel: { color: theme.textDim, flex: 1, fontSize: 13 },
  routeActive: { fontSize: 12, fontWeight: "700" },
  team: { marginTop: 12, borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: theme.border, paddingTop: 8 },
  teamName: { color: theme.accent, fontWeight: "700", fontSize: 13, marginBottom: 4 },
  member: { flexDirection: "row", alignItems: "center", paddingVertical: 6 },
  memberName: { color: theme.text, fontSize: 15, fontWeight: "600" },
  memberTitle: { color: theme.textDim, fontSize: 12, marginTop: 1 },
  task: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 10, paddingVertical: 8, borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: theme.border },
  taskTitle: { color: theme.text, fontSize: 14, flex: 1 },
  note: { color: theme.textDim, fontSize: 11, marginTop: 10, lineHeight: 16 },
  dim: { color: theme.textDim },
});
