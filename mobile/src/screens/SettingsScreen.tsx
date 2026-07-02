import React, { useEffect, useState } from "react";
import { View, Text, TextInput, TouchableOpacity, StyleSheet } from "react-native";
import { Screen, Card } from "../components";
import { getApiBase, setApiBase, api, ApiError, clearToken, User } from "../api";
import { theme } from "../theme";

export default function SettingsScreen({ onLogout }: { onLogout?: () => void }) {
  const [base, setBase] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [ok, setOk] = useState<boolean | null>(null);
  const [checking, setChecking] = useState(false);
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    getApiBase().then(setBase);
    api.me().then(setUser).catch(() => setUser(null));
  }, []);

  async function logout() {
    await clearToken();
    onLogout?.();
  }

  async function save() {
    await setApiBase(base);
    setStatus("Saved.");
    setOk(null);
  }

  async function test() {
    setChecking(true);
    setStatus(null);
    try {
      await setApiBase(base);
      const h = await api.health();
      setOk(h.status === "ok");
      setStatus(`Health: ${h.status} · db ${h.db}`);
    } catch (e) {
      setOk(false);
      setStatus(e instanceof ApiError ? e.message : String(e));
    } finally {
      setChecking(false);
    }
  }

  return (
    <Screen>
      <Card title="Account">
        <Text style={s.acctName}>{user?.display_name || user?.email || "Signed in"}</Text>
        {user?.email ? <Text style={s.hint}>{user.email}</Text> : null}
        <TouchableOpacity style={[s.btn, s.btnGhost, { marginTop: 14 }]} onPress={logout}>
          <Text style={s.btnGhostText}>Log out</Text>
        </TouchableOpacity>
      </Card>

      <Card title="Backend connection">
        <Text style={s.label}>API base URL</Text>
        <TextInput
          value={base}
          onChangeText={setBase}
          autoCapitalize="none"
          autoCorrect={false}
          keyboardType="url"
          placeholder="http://mini-a.tailnet.ts.net:8000"
          placeholderTextColor={theme.textDim}
          style={s.input}
        />
        <Text style={s.hint}>
          Point this at your Mini-A over Tailscale (MagicDNS name or 100.x address). Must be on the
          same tailnet. No trailing slash needed.
        </Text>

        <View style={s.btnRow}>
          <TouchableOpacity style={[s.btn, s.btnPrimary]} onPress={save}>
            <Text style={s.btnPrimaryText}>Save</Text>
          </TouchableOpacity>
          <TouchableOpacity style={[s.btn, s.btnGhost]} onPress={test} disabled={checking}>
            <Text style={s.btnGhostText}>{checking ? "Testing…" : "Test connection"}</Text>
          </TouchableOpacity>
        </View>

        {status ? (
          <Text style={[s.status, { color: ok === false ? theme.bad : ok === true ? theme.good : theme.textDim }]}>
            {status}
          </Text>
        ) : null}
      </Card>

      <Card title="About">
        <Text style={s.hint}>
          Aadyon Assist — your personal life-ops assistant. The Assistant tab can read and directly
          update your own data. Anything with a real-world side effect (money, email, filings) is
          queued as a proposal for your approval and never auto-executes.
        </Text>
      </Card>
    </Screen>
  );
}

const s = StyleSheet.create({
  acctName: { color: theme.text, fontSize: 16, fontWeight: "700" },
  label: { color: theme.textDim, fontSize: 12, marginBottom: 6 },
  input: {
    backgroundColor: theme.cardAlt,
    borderWidth: 1,
    borderColor: theme.border,
    borderRadius: 10,
    color: theme.text,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 15,
  },
  hint: { color: theme.textDim, fontSize: 12, marginTop: 8, lineHeight: 17 },
  btnRow: { flexDirection: "row", gap: 10, marginTop: 14 },
  btn: { flex: 1, borderRadius: 10, paddingVertical: 11, alignItems: "center" },
  btnPrimary: { backgroundColor: theme.accent },
  btnPrimaryText: { color: "#06122a", fontWeight: "800" },
  btnGhost: { borderWidth: 1, borderColor: theme.border },
  btnGhostText: { color: theme.text, fontWeight: "700" },
  status: { marginTop: 12, fontSize: 13 },
});
