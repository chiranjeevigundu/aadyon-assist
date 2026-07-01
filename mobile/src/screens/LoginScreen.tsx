import React, { useEffect, useState } from "react";
import {
  View, Text, TextInput, TouchableOpacity, StyleSheet, KeyboardAvoidingView, Platform,
} from "react-native";
import { getApiBase, setApiBase, setToken, api, ApiError } from "../api";
import { theme } from "../theme";

// Gates the app. On success it stores the JWT and calls onAuthed() so App swaps
// in the tab navigator. Supports both sign-in and account creation.
export default function LoginScreen({ onAuthed }: { onAuthed: () => void }) {
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [base, setBase] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    getApiBase().then(setBase);
  }, []);

  async function submit() {
    setBusy(true);
    setErr(null);
    try {
      await setApiBase(base);
      const res =
        mode === "login"
          ? await api.login(email.trim(), password)
          : await api.signup(email.trim(), password, name.trim() || undefined);
      await setToken(res.token);
      onAuthed();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <KeyboardAvoidingView
      behavior={Platform.OS === "ios" ? "padding" : undefined}
      style={s.wrap}
    >
      <View style={s.inner}>
        <Text style={s.brand}>Aadyon</Text>
        <Text style={s.tagline}>Your life-ops assistant</Text>

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

        {mode === "signup" ? (
          <>
            <Text style={s.label}>Name</Text>
            <TextInput
              value={name}
              onChangeText={setName}
              placeholder="Your name"
              placeholderTextColor={theme.textDim}
              style={s.input}
            />
          </>
        ) : null}

        <Text style={s.label}>Email</Text>
        <TextInput
          value={email}
          onChangeText={setEmail}
          autoCapitalize="none"
          autoCorrect={false}
          keyboardType="email-address"
          placeholder="you@example.com"
          placeholderTextColor={theme.textDim}
          style={s.input}
        />

        <Text style={s.label}>Password</Text>
        <TextInput
          value={password}
          onChangeText={setPassword}
          secureTextEntry
          placeholder={mode === "signup" ? "At least 8 characters" : "••••••••"}
          placeholderTextColor={theme.textDim}
          style={s.input}
        />

        {err ? <Text style={s.err}>{err}</Text> : null}

        <TouchableOpacity style={[s.btn, s.btnPrimary]} onPress={submit} disabled={busy}>
          <Text style={s.btnPrimaryText}>
            {busy ? "…" : mode === "login" ? "Sign in" : "Create account"}
          </Text>
        </TouchableOpacity>

        <TouchableOpacity onPress={() => { setErr(null); setMode(mode === "login" ? "signup" : "login"); }}>
          <Text style={s.switch}>
            {mode === "login" ? "No account? Create one" : "Have an account? Sign in"}
          </Text>
        </TouchableOpacity>
      </View>
    </KeyboardAvoidingView>
  );
}

const s = StyleSheet.create({
  wrap: { flex: 1, backgroundColor: theme.bg, justifyContent: "center" },
  inner: { padding: 24 },
  brand: { color: theme.text, fontSize: 34, fontWeight: "900", textAlign: "center" },
  tagline: { color: theme.textDim, textAlign: "center", marginTop: 4, marginBottom: 24 },
  label: { color: theme.textDim, fontSize: 12, marginBottom: 6, marginTop: 12 },
  input: {
    backgroundColor: theme.cardAlt,
    borderWidth: 1,
    borderColor: theme.border,
    borderRadius: 10,
    color: theme.text,
    paddingHorizontal: 12,
    paddingVertical: 12,
    fontSize: 15,
  },
  err: { color: theme.bad, marginTop: 14, fontSize: 13 },
  btn: { borderRadius: 10, paddingVertical: 13, alignItems: "center", marginTop: 22 },
  btnPrimary: { backgroundColor: theme.accent },
  btnPrimaryText: { color: "#06122a", fontWeight: "800", fontSize: 16 },
  switch: { color: theme.accent, textAlign: "center", marginTop: 18, fontWeight: "600" },
});
