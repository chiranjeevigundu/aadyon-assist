// Mail integrations — mirrors the web dashboard's accounts page (dashboard/assets/accounts.js).
// Connect mailboxes (IMAP app password or Microsoft device-code), sync read-only, and review
// what the pipeline found. Everything found waits for an explicit approve (golden rule #2).
import React, { useCallback, useEffect, useRef, useState } from "react";
import { View, Text, TextInput, TouchableOpacity, StyleSheet, Alert, Linking } from "react-native";
import { Screen, Card, Loading, ErrorBox, Pill } from "../components";
import { api, ApiError, EmailAccount, EmailExtraction, MsDeviceCode } from "../api";
import { theme } from "../theme";

const PROVIDERS = [
  { key: "icloud", label: "iCloud", auth: "imap", host: "imap.mail.me.com" },
  { key: "gmail", label: "Gmail", auth: "oauth_google", host: "imap.gmail.com" },
  { key: "microsoft", label: "Microsoft", auth: "oauth_microsoft", host: "outlook.office365.com" },
  { key: "other", label: "Other (IMAP)", auth: "imap", host: null },
];

const AUTHS = [
  { key: "imap", label: "IMAP (app password)" },
  { key: "oauth_google", label: "OAuth · Google" },
  { key: "oauth_microsoft", label: "OAuth · Microsoft" },
];

const statusColor = (s?: string | null) =>
  s === "connected" ? theme.good : s === "error" ? theme.bad : theme.textDim;
const kindColor = (k?: string | null) =>
  k === "bill" ? theme.bad : k === "deadline" ? theme.watch : k === "subscription" ? theme.accent : theme.textDim;
const errMsg = (e: unknown) => (e instanceof ApiError ? e.message : String(e));

function Btn({
  label,
  onPress,
  disabled,
  primary,
  danger,
}: {
  label: string;
  onPress?: () => void;
  disabled?: boolean;
  primary?: boolean;
  danger?: boolean;
}) {
  return (
    <TouchableOpacity
      onPress={onPress}
      disabled={disabled}
      style={[s.btn, primary && s.btnPrimary, danger && s.btnDanger, disabled && { opacity: 0.5 }]}
    >
      <Text style={[s.btnText, primary && s.btnTextPrimary, danger && s.btnTextDanger]}>{label}</Text>
    </TouchableOpacity>
  );
}

export default function MailScreen() {
  const [accounts, setAccounts] = useState<EmailAccount[] | null>(null);
  const [exts, setExts] = useState<EmailExtraction[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null); // id with an in-flight action

  // Add-account form
  const [email, setEmail] = useState("");
  const [purpose, setPurpose] = useState("");
  const [provider, setProvider] = useState("icloud");
  const [authType, setAuthType] = useState("imap");
  const [adding, setAdding] = useState(false);

  // IMAP connect panel (one open at a time)
  const [connectId, setConnectId] = useState<string | null>(null);
  const [password, setPassword] = useState("");

  // Microsoft device-code flow
  const [ms, setMs] = useState<{ id: string; code: MsDeviceCode; status: string } | null>(null);
  const msTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const stopMsPolling = () => {
    if (msTimer.current) {
      clearTimeout(msTimer.current);
      msTimer.current = null;
    }
  };
  useEffect(() => stopMsPolling, []);

  // The note doubles as the dashboard's toast — clear it after a beat.
  useEffect(() => {
    if (!note) return;
    const t = setTimeout(() => setNote(null), 5000);
    return () => clearTimeout(t);
  }, [note]);

  const load = useCallback(async () => {
    try {
      const [a, x] = await Promise.all([api.emailAccounts(), api.emailExtractions("pending")]);
      setAccounts(a);
      setExts(x);
      setError(null);
    } catch (e) {
      setError(errMsg(e));
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function refresh() {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  }

  async function addAccount() {
    const em = email.trim();
    if (!em) {
      Alert.alert("Enter an email address");
      return;
    }
    const prov = PROVIDERS.find((p) => p.key === provider);
    setAdding(true);
    try {
      await api.addEmailAccount({
        email: em,
        provider,
        purpose: purpose.trim() || null,
        auth_type: authType,
        status: "not_connected",
        imap_host: prov?.host ?? null,
        imap_port: 993,
      });
      setEmail("");
      setPurpose("");
      setNote("Account added — connect it below.");
      await load();
    } catch (e) {
      Alert.alert("Couldn't add account", errMsg(e));
    } finally {
      setAdding(false);
    }
  }

  async function saveConnect(id: string) {
    const pw = password.trim();
    if (!pw) {
      Alert.alert("Enter the app-specific password");
      return;
    }
    setBusy(id);
    try {
      await api.emailConnect(id, pw);
      setConnectId(null);
      setPassword("");
      setNote("Connected ✓");
      await load();
    } catch (e) {
      Alert.alert("Connect failed", errMsg(e));
    } finally {
      setBusy(null);
    }
  }

  async function msConnect(id: string) {
    stopMsPolling();
    setBusy(id);
    try {
      const code = await api.emailMsStart(id);
      setMs({ id, code, status: "Waiting for you to approve…" });
      const deadline = Date.now() + code.expires_in * 1000;
      const tick = async () => {
        if (Date.now() > deadline) {
          setMs((m) => (m && m.id === id ? { ...m, status: "Code expired — tap Connect again." } : m));
          return;
        }
        try {
          const r = await api.emailMsComplete(id, code.device_code);
          if (r.status === "connected") {
            setMs(null);
            setNote("Microsoft connected ✓");
            await load();
            return;
          }
        } catch (e) {
          setMs((m) => (m && m.id === id ? { ...m, status: errMsg(e) } : m));
          return;
        }
        msTimer.current = setTimeout(tick, (code.interval || 5) * 1000);
      };
      msTimer.current = setTimeout(tick, (code.interval || 5) * 1000);
    } catch (e) {
      Alert.alert("Microsoft sign-in failed", errMsg(e));
    } finally {
      setBusy(null);
    }
  }

  async function sync(id: string) {
    setBusy(id);
    try {
      const r = await api.emailSync(id);
      setNote(`Scanned ${r.scanned ?? 0} messages, queued ${r.queued ?? 0} for review.`);
      await load();
    } catch (e) {
      Alert.alert("Sync failed", errMsg(e));
    } finally {
      setBusy(null);
    }
  }

  function disconnect(id: string) {
    Alert.alert("Disconnect?", "The stored credentials are forgotten; the account entry stays.", [
      { text: "Cancel", style: "cancel" },
      {
        text: "Disconnect",
        style: "destructive",
        onPress: async () => {
          try {
            await api.emailDisconnect(id);
            setNote("Disconnected.");
            await load();
          } catch (e) {
            Alert.alert("Disconnect failed", errMsg(e));
          }
        },
      },
    ]);
  }

  function removeAccount(id: string) {
    Alert.alert("Remove this account?", "The account entry and its stored credentials are deleted.", [
      { text: "Cancel", style: "cancel" },
      {
        text: "Remove",
        style: "destructive",
        onPress: async () => {
          try {
            await api.deleteEmailAccount(id);
            setNote("Account removed.");
            await load();
          } catch (e) {
            Alert.alert("Remove failed", errMsg(e));
          }
        },
      },
    ]);
  }

  async function approve(id: string) {
    setBusy(id);
    try {
      const r = await api.approveExtraction(id);
      setNote(`Added as ${r.applied_as || "a tracked item"} ✓`);
      await load();
    } catch (e) {
      Alert.alert("Approve failed", errMsg(e));
    } finally {
      setBusy(null);
    }
  }

  async function dismiss(id: string) {
    setBusy(id);
    try {
      await api.dismissExtraction(id);
      await load();
    } catch (e) {
      Alert.alert("Dismiss failed", errMsg(e));
    } finally {
      setBusy(null);
    }
  }

  if (error && !accounts) {
    return (
      <Screen refreshing={refreshing} onRefresh={refresh}>
        <ErrorBox message={error} />
      </Screen>
    );
  }
  if (!accounts) {
    return (
      <View style={{ flex: 1, backgroundColor: theme.bg }}>
        <Loading label="Loading accounts…" />
      </View>
    );
  }

  return (
    <Screen refreshing={refreshing} onRefresh={refresh}>
      <Card>
        <Text style={s.hint}>
          <Text style={{ fontWeight: "700", color: theme.text }}>iCloud: </Text>
          generate an app-specific password at appleid.apple.com → Sign-In &amp; Security →
          App-Specific Passwords, then Connect below and paste it. It's encrypted at rest; mail is
          read-only and found items queue for your approval. (Gmail OAuth comes later.)
        </Text>
      </Card>

      {note ? <Text style={s.note}>{note}</Text> : null}

      <Card title="Your accounts">
        {accounts.length === 0 ? (
          <Text style={s.empty}>No accounts yet — add one below.</Text>
        ) : (
          accounts.map((a) => {
            const connected = a.status === "connected";
            const isBusy = busy === a.id;
            return (
              <View key={a.id} style={s.acct}>
                <View style={s.acctTop}>
                  <View style={{ flex: 1 }}>
                    <Text style={s.who}>{a.email}</Text>
                    <Text style={s.meta}>
                      {a.provider}
                      {a.purpose ? ` · ${a.purpose}` : ""} · {a.auth_type}
                      {a.last_sync ? ` · synced ${String(a.last_sync).slice(0, 16).replace("T", " ")}` : ""}
                    </Text>
                    {a.last_error ? <Text style={[s.meta, { color: theme.bad }]}>{a.last_error}</Text> : null}
                  </View>
                  <Pill text={a.status || "not_connected"} color={statusColor(a.status)} />
                </View>

                <View style={s.btnRow}>
                  {connected ? (
                    <>
                      <Btn label={isBusy ? "Syncing…" : "Sync now"} onPress={() => sync(a.id)} disabled={isBusy} primary />
                      <Btn label="Disconnect" onPress={() => disconnect(a.id)} disabled={isBusy} />
                    </>
                  ) : a.auth_type === "imap" ? (
                    <Btn
                      label={connectId === a.id ? "Hide" : "Connect"}
                      onPress={() => {
                        setConnectId(connectId === a.id ? null : a.id);
                        setPassword("");
                      }}
                      primary
                    />
                  ) : a.auth_type === "oauth_microsoft" ? (
                    <Btn
                      label={isBusy ? "Starting…" : "Connect (Microsoft)"}
                      onPress={() => msConnect(a.id)}
                      disabled={isBusy}
                      primary
                    />
                  ) : (
                    <Btn label="Gmail OAuth soon" disabled />
                  )}
                  <Btn label="Remove" onPress={() => removeAccount(a.id)} disabled={isBusy} danger />
                </View>

                {connectId === a.id && !connected ? (
                  <View style={s.connect}>
                    <Text style={s.label}>App-specific password for {a.email}</Text>
                    <TextInput
                      value={password}
                      onChangeText={setPassword}
                      secureTextEntry
                      autoCapitalize="none"
                      autoCorrect={false}
                      placeholder="xxxx-xxxx-xxxx-xxxx"
                      placeholderTextColor={theme.textDim}
                      style={s.input}
                    />
                    <View style={s.btnRow}>
                      <Btn label={isBusy ? "Connecting…" : "Save & connect"} onPress={() => saveConnect(a.id)} disabled={isBusy} primary />
                      <Btn
                        label="Cancel"
                        onPress={() => {
                          setConnectId(null);
                          setPassword("");
                        }}
                      />
                    </View>
                    <Text style={s.metaHint}>Stored encrypted; verified by a test login before saving.</Text>
                  </View>
                ) : null}

                {ms && ms.id === a.id ? (
                  <View style={s.connect}>
                    <Text style={s.msCode}>{ms.code.user_code}</Text>
                    <Text style={s.metaHint}>
                      Enter this code at the Microsoft sign-in page, sign in and approve access.
                    </Text>
                    <View style={s.btnRow}>
                      <Btn label="Open Microsoft sign-in" onPress={() => Linking.openURL(ms.code.verification_uri)} primary />
                      <Btn
                        label="Cancel"
                        onPress={() => {
                          stopMsPolling();
                          setMs(null);
                        }}
                      />
                    </View>
                    <Text style={s.metaHint}>{ms.status}</Text>
                  </View>
                ) : null}
              </View>
            );
          })
        )}
      </Card>

      <Card title="Found in your mail — review">
        {!exts || exts.length === 0 ? (
          <Text style={s.empty}>Nothing pending. Hit "Sync now" on a connected account.</Text>
        ) : (
          exts.map((x) => (
            <View key={x.id} style={s.acct}>
              <View style={{ flexDirection: "row", alignItems: "center", gap: 8, marginBottom: 4 }}>
                <Pill text={x.kind || "item"} color={kindColor(x.kind)} />
                <Text style={[s.who, { flex: 1 }]} numberOfLines={2}>
                  {x.payload?.title || x.subject || "(item)"}
                </Text>
              </View>
              {x.summary ? <Text style={s.meta}>{x.summary}</Text> : null}
              <Text style={s.meta}>
                from {x.sender || "?"}
                {x.account_email ? ` · ${x.account_email}` : ""}
              </Text>
              <View style={s.btnRow}>
                <Btn label="Approve" onPress={() => approve(x.id)} disabled={busy === x.id} primary />
                <Btn label="Dismiss" onPress={() => dismiss(x.id)} disabled={busy === x.id} danger />
              </View>
            </View>
          ))
        )}
      </Card>

      <Card title="Add an account">
        <Text style={s.label}>Email address</Text>
        <TextInput
          value={email}
          onChangeText={setEmail}
          autoCapitalize="none"
          autoCorrect={false}
          keyboardType="email-address"
          placeholder="you@icloud.com"
          placeholderTextColor={theme.textDim}
          style={s.input}
        />
        <Text style={[s.label, { marginTop: 12 }]}>Purpose</Text>
        <TextInput
          value={purpose}
          onChangeText={setPurpose}
          placeholder="University / Personal / Finance"
          placeholderTextColor={theme.textDim}
          style={s.input}
        />
        <Text style={[s.label, { marginTop: 12 }]}>Provider</Text>
        <View style={s.chips}>
          {PROVIDERS.map((p) => (
            <TouchableOpacity
              key={p.key}
              style={[s.chip, provider === p.key && s.chipOn]}
              onPress={() => {
                setProvider(p.key);
                setAuthType(p.auth);
              }}
            >
              <Text style={[s.chipText, provider === p.key && s.chipTextOn]}>{p.label}</Text>
            </TouchableOpacity>
          ))}
        </View>
        <Text style={[s.label, { marginTop: 12 }]}>Auth method</Text>
        <View style={s.chips}>
          {AUTHS.map((m) => (
            <TouchableOpacity
              key={m.key}
              style={[s.chip, authType === m.key && s.chipOn]}
              onPress={() => setAuthType(m.key)}
            >
              <Text style={[s.chipText, authType === m.key && s.chipTextOn]}>{m.label}</Text>
            </TouchableOpacity>
          ))}
        </View>
        <View style={[s.btnRow, { marginTop: 14 }]}>
          <Btn label={adding ? "Adding…" : "Add account"} onPress={addAccount} disabled={adding} primary />
        </View>
      </Card>
    </Screen>
  );
}

const s = StyleSheet.create({
  hint: { color: theme.textDim, fontSize: 13, lineHeight: 18 },
  note: { color: theme.good, fontSize: 13, marginBottom: 10, marginLeft: 2 },
  empty: { color: theme.textDim, fontSize: 13 },
  acct: {
    backgroundColor: theme.cardAlt,
    borderWidth: 1,
    borderColor: theme.border,
    borderRadius: 10,
    padding: 12,
    marginBottom: 10,
  },
  acctTop: { flexDirection: "row", alignItems: "center", gap: 10 },
  who: { color: theme.text, fontSize: 15, fontWeight: "700" },
  meta: { color: theme.textDim, fontSize: 12, marginTop: 2 },
  metaHint: { color: theme.textDim, fontSize: 12, marginTop: 8, lineHeight: 17 },
  label: { color: theme.textDim, fontSize: 12, marginBottom: 6 },
  input: {
    backgroundColor: theme.bg,
    borderWidth: 1,
    borderColor: theme.border,
    borderRadius: 10,
    color: theme.text,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 15,
  },
  btnRow: { flexDirection: "row", gap: 8, marginTop: 10, flexWrap: "wrap" },
  btn: {
    borderWidth: 1,
    borderColor: theme.border,
    borderRadius: 10,
    paddingVertical: 8,
    paddingHorizontal: 14,
    alignItems: "center",
  },
  btnPrimary: { backgroundColor: theme.accent, borderColor: theme.accent },
  btnDanger: { borderColor: theme.bad },
  btnText: { color: theme.text, fontWeight: "700", fontSize: 13 },
  btnTextPrimary: { color: "#06122a" },
  btnTextDanger: { color: theme.bad },
  connect: {
    marginTop: 10,
    borderTopWidth: 1,
    borderTopColor: theme.border,
    paddingTop: 10,
  },
  msCode: {
    color: theme.text,
    fontSize: 24,
    fontWeight: "800",
    letterSpacing: 4,
    textAlign: "center",
    marginVertical: 6,
  },
  chips: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  chip: {
    borderWidth: 1,
    borderColor: theme.border,
    borderRadius: 999,
    paddingVertical: 6,
    paddingHorizontal: 12,
  },
  chipOn: { borderColor: theme.accent, backgroundColor: "rgba(91,156,255,0.12)" },
  chipText: { color: theme.textDim, fontSize: 13, fontWeight: "600" },
  chipTextOn: { color: theme.accent },
});
