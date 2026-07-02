// Small reusable UI pieces shared across screens.
import React from "react";
import { View, Text, StyleSheet, ActivityIndicator, ScrollView, RefreshControl } from "react-native";
import { theme, scoreColor } from "./theme";

export function Card({ title, children, style }: { title?: string; children?: React.ReactNode; style?: any }) {
  return (
    <View style={[styles.card, style]}>
      {title ? <Text style={styles.cardTitle}>{title}</Text> : null}
      {children}
    </View>
  );
}

export function Row({ label, value, dim }: { label: string; value?: any; dim?: boolean }) {
  if (value === null || value === undefined || value === "") return null;
  return (
    <View style={styles.row}>
      <Text style={styles.rowLabel}>{label}</Text>
      <Text style={[styles.rowValue, dim && { color: theme.textDim }]} numberOfLines={2}>
        {String(value)}
      </Text>
    </View>
  );
}

// A circular-ish score badge.
export function ScoreBadge({ score, size = 64 }: { score: number; size?: number }) {
  const color = scoreColor(score);
  return (
    <View
      style={{
        width: size,
        height: size,
        borderRadius: size / 2,
        borderWidth: 3,
        borderColor: color,
        alignItems: "center",
        justifyContent: "center",
        backgroundColor: theme.cardAlt,
      }}
    >
      <Text style={{ color, fontSize: size * 0.34, fontWeight: "800" }}>{Math.round(score)}</Text>
    </View>
  );
}

export function Pill({ text, color }: { text: string; color: string }) {
  return (
    <View style={[styles.pill, { borderColor: color }]}>
      <Text style={{ color, fontSize: 12, fontWeight: "700" }}>{text}</Text>
    </View>
  );
}

export function Loading({ label }: { label?: string }) {
  return (
    <View style={styles.center}>
      <ActivityIndicator color={theme.accent} />
      {label ? <Text style={styles.dim}>{label}</Text> : null}
    </View>
  );
}

export function ErrorBox({ message }: { message: string }) {
  return (
    <View style={[styles.card, { borderColor: theme.bad }]}>
      <Text style={{ color: theme.bad, fontWeight: "700", marginBottom: 4 }}>Couldn't load</Text>
      <Text style={{ color: theme.textDim }}>{message}</Text>
      <Text style={{ color: theme.textDim, marginTop: 8, fontSize: 12 }}>
        Pull down to retry. Set your API URL in the Settings tab.
      </Text>
    </View>
  );
}

// A screen wrapper with pull-to-refresh.
export function Screen({
  children,
  refreshing,
  onRefresh,
}: {
  children: React.ReactNode;
  refreshing?: boolean;
  onRefresh?: () => void;
}) {
  return (
    <ScrollView
      style={{ backgroundColor: theme.bg }}
      contentContainerStyle={{ padding: 14, paddingBottom: 40 }}
      refreshControl={
        onRefresh ? (
          <RefreshControl refreshing={!!refreshing} onRefresh={onRefresh} tintColor={theme.accent} />
        ) : undefined
      }
    >
      {children}
    </ScrollView>
  );
}

export const styles = StyleSheet.create({
  card: {
    backgroundColor: theme.card,
    borderRadius: 14,
    padding: 14,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: theme.border,
  },
  cardTitle: { color: theme.textDim, fontSize: 12, fontWeight: "700", textTransform: "uppercase", letterSpacing: 1, marginBottom: 10 },
  row: { flexDirection: "row", justifyContent: "space-between", paddingVertical: 6, gap: 12 },
  rowLabel: { color: theme.textDim, fontSize: 14, flexShrink: 0 },
  rowValue: { color: theme.text, fontSize: 14, fontWeight: "600", flexShrink: 1, textAlign: "right" },
  pill: { borderWidth: 1, borderRadius: 999, paddingHorizontal: 10, paddingVertical: 3 },
  center: { padding: 40, alignItems: "center", justifyContent: "center", gap: 10 },
  dim: { color: theme.textDim },
});
