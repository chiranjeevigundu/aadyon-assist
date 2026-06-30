import React, { useCallback, useEffect, useState } from "react";
import { View, Text, StyleSheet } from "react-native";
import { Screen, Card, Pill, Loading, ErrorBox } from "../components";
import { api, Summary } from "../api";
import { theme } from "../theme";

export default function TrackerScreen() {
  const [data, setData] = useState<Summary | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    try {
      setErr(null);
      setData(await api.summary());
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

  if (loading) return <Loading label="Loading tracker…" />;
  const refresh = () => { setRefreshing(true); load(); };
  if (err && !data) return <Screen onRefresh={refresh} refreshing={refreshing}><ErrorBox message={err} /></Screen>;

  const d = data!;
  const t = d.debt_totals || {};

  return (
    <Screen onRefresh={refresh} refreshing={refreshing}>
      {/* Debt snapshot */}
      <Card title="Debt">
        <Big label="Total balance" value={money(t.total_debt)} />
        <View style={s.statRow}>
          <Stat label="Min payments" value={money(t.total_min_payments)} />
          <Stat label="Interest / mo" value={money(t.est_monthly_interest)} />
        </View>
      </Card>

      {/* Deadlines */}
      <Section title="Deadlines" count={d.deadlines?.length}>
        {(d.deadlines || []).slice(0, 12).map((x, i) => (
          <Item
            key={i}
            title={x.title}
            sub={[x.category, x.due_date].filter(Boolean).join(" · ")}
            right={daysLeft(x.days_left ?? x.due_date)}
            rightColor={urgency(x.days_left)}
          />
        ))}
        {!d.deadlines?.length && <Empty />}
      </Section>

      {/* Bills */}
      <Section title="Bills" count={d.bills?.length}>
        {(d.bills || []).map((x, i) => (
          <Item key={i} title={x.name} sub={billSub(x)} right={money(x.amount)} />
        ))}
        {!d.bills?.length && <Empty />}
      </Section>

      {/* Subscriptions */}
      <Section title="Subscriptions" count={d.subscriptions?.length}>
        {(d.subscriptions || []).map((x, i) => (
          <Item
            key={i}
            title={x.name}
            sub={[x.billing_cycle, x.renews_on && `renews ${x.renews_on}`].filter(Boolean).join(" · ")}
            right={money(x.amount)}
          />
        ))}
        {!d.subscriptions?.length && <Empty />}
      </Section>

      {/* Shifts */}
      <Section title="Recent shifts" count={d.shifts?.length}>
        {(d.shifts || []).slice(0, 10).map((x, i) => (
          <Item
            key={i}
            title={[x.employer, x.role].filter(Boolean).join(" · ") || "Shift"}
            sub={[x.shift_date, x.hours && `${x.hours}h`].filter(Boolean).join(" · ")}
            right={money(x.est_pay)}
          />
        ))}
        {!d.shifts?.length && <Empty />}
      </Section>
    </Screen>
  );
}

function Section({ title, count, children }: { title: string; count?: number; children: React.ReactNode }) {
  return (
    <Card>
      <View style={s.secHead}>
        <Text style={s.secTitle}>{title}</Text>
        {count !== undefined ? <Text style={s.secCount}>{count}</Text> : null}
      </View>
      {children}
    </Card>
  );
}

function Item({ title, sub, right, rightColor }: { title: string; sub?: string; right?: string; rightColor?: string }) {
  return (
    <View style={s.item}>
      <View style={{ flex: 1, paddingRight: 10 }}>
        <Text style={s.itemTitle} numberOfLines={1}>{title || "—"}</Text>
        {sub ? <Text style={s.itemSub} numberOfLines={1}>{sub}</Text> : null}
      </View>
      {right ? <Text style={[s.itemRight, rightColor && { color: rightColor }]}>{right}</Text> : null}
    </View>
  );
}

function Big({ label, value }: { label: string; value: string }) {
  return (
    <View style={{ marginBottom: 8 }}>
      <Text style={s.bigLabel}>{label}</Text>
      <Text style={s.bigValue}>{value}</Text>
    </View>
  );
}
function Stat({ label, value }: { label: string; value: string }) {
  return (
    <View style={{ flex: 1 }}>
      <Text style={s.statLabel}>{label}</Text>
      <Text style={s.statValue}>{value}</Text>
    </View>
  );
}
function Empty() {
  return <Text style={s.empty}>Nothing here.</Text>;
}

// ---- helpers ----
function money(v: any) {
  const n = Number(v);
  if (v === null || v === undefined || isNaN(n)) return "—";
  return `$${n.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
}
function billSub(x: any) {
  return [x.frequency, x.due_day && `day ${x.due_day}`, x.autopay && "autopay"].filter(Boolean).join(" · ");
}
function daysLeft(v: any) {
  const n = Number(v);
  if (isNaN(n)) return v ? String(v) : "—";
  if (n < 0) return `${Math.abs(n)}d ago`;
  if (n === 0) return "today";
  return `${n}d`;
}
function urgency(days: any) {
  const n = Number(days);
  if (isNaN(n)) return undefined;
  if (n <= 3) return theme.bad;
  if (n <= 10) return theme.watch;
  return theme.good;
}

const s = StyleSheet.create({
  statRow: { flexDirection: "row", gap: 12, marginTop: 4 },
  bigLabel: { color: theme.textDim, fontSize: 12 },
  bigValue: { color: theme.text, fontSize: 28, fontWeight: "800" },
  statLabel: { color: theme.textDim, fontSize: 12 },
  statValue: { color: theme.text, fontSize: 17, fontWeight: "700", marginTop: 2 },
  secHead: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 6 },
  secTitle: { color: theme.textDim, fontSize: 12, fontWeight: "700", letterSpacing: 1, textTransform: "uppercase" },
  secCount: { color: theme.textDim, fontSize: 12, fontWeight: "700" },
  item: { flexDirection: "row", alignItems: "center", paddingVertical: 9, borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: theme.border },
  itemTitle: { color: theme.text, fontSize: 15, fontWeight: "600" },
  itemSub: { color: theme.textDim, fontSize: 12, marginTop: 2 },
  itemRight: { color: theme.text, fontSize: 14, fontWeight: "700" },
  empty: { color: theme.textDim, fontStyle: "italic", paddingVertical: 6 },
});
