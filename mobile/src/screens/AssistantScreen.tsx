import React, { useCallback, useRef, useState } from "react";
import {
  View, Text, TextInput, TouchableOpacity, StyleSheet, FlatList,
  KeyboardAvoidingView, Platform, ActivityIndicator,
} from "react-native";
import { api, ApiError, ChatResult } from "../api";
import { theme } from "../theme";
import * as Speech from "expo-speech";
import { useSpeechRecognitionEvent, ExpoSpeechRecognitionModule } from "expo-speech-recognition";

type Msg = {
  id: string;
  role: "user" | "assistant";
  text: string;
  actions?: string[];
  proposals?: { id: string; title?: string }[];
};

let _seq = 0;
const nextId = () => `m${_seq++}`;

// Jarvis: a conversational tab that can read AND write your data. It talks to
// POST /api/assistant/chat; the assistant edits your records directly, while
// money/email/filing actions come back as proposals to approve on the web console.
export default function AssistantScreen() {
  const [messages, setMessages] = useState<Msg[]>([
    {
      id: nextId(),
      role: "assistant",
      text:
        "Hi — I'm your life-ops assistant. Ask me about your finances, visa, or goals, " +
        "or tell me to update things (e.g. \"add a deadline to renew my passport next month\").",
    },
  ]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [recognizing, setRecognizing] = useState(false);
  const convId = useRef<string | undefined>(undefined);
  const listRef = useRef<FlatList<Msg>>(null);

  const scroll = () => setTimeout(() => listRef.current?.scrollToEnd({ animated: true }), 50);

  useSpeechRecognitionEvent("start", () => setRecognizing(true));
  useSpeechRecognitionEvent("end", () => setRecognizing(false));
  useSpeechRecognitionEvent("result", (event) => {
    const transcript = event.results[0]?.transcript || "";
    setInput(transcript);
  });
  useSpeechRecognitionEvent("error", (event) => {
    console.log("Speech recognition error:", event.error, event.message);
    setRecognizing(false);
  });

  const toggleListening = async () => {
    if (recognizing) {
      ExpoSpeechRecognitionModule.stop();
      return;
    }
    const result = await ExpoSpeechRecognitionModule.requestPermissionsAsync();
    if (!result.granted) {
      alert("Microphone permission is required for voice commands.");
      return;
    }
    Speech.stop();
    ExpoSpeechRecognitionModule.start({
      lang: "en-US",
      interimResults: true,
      maxAlternatives: 1,
      continuous: false,
    });
  };

  const send = useCallback(async () => {
    const text = input.trim();
    if (!text || busy) return;
    
    if (recognizing) ExpoSpeechRecognitionModule.stop();
    Speech.stop();
    
    setInput("");
    setMessages((m) => [...m, { id: nextId(), role: "user", text }]);
    setBusy(true);
    scroll();
    try {
      const botId = nextId();
      setMessages((m) => [...m, { id: botId, role: "assistant", text: "" }]);
      
      const res: ChatResult = await api.chatStream(text, convId.current, (chunk) => {
        if (chunk.delta) {
          setMessages((m) =>
            m.map((msg) =>
              msg.id === botId ? { ...msg, text: msg.text + chunk.delta } : msg
            )
          );
        }
      });
      
      convId.current = res.conversation_id;
      setMessages((m) =>
        m.map((msg) =>
          msg.id === botId
            ? { ...msg, actions: res.actions, proposals: res.proposals }
            : msg
        )
      );
      
      if (res.reply) {
        Speech.speak(res.reply);
      }
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : String(e);
      setMessages((m) => [...m, { id: nextId(), role: "assistant", text: `⚠️ ${msg}` }]);
    } finally {
      setBusy(false);
      scroll();
    }
  }, [input, busy, recognizing]);

  return (
    <KeyboardAvoidingView
      style={s.wrap}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
      keyboardVerticalOffset={90}
    >
      <FlatList
        ref={listRef}
        data={messages}
        keyExtractor={(m) => m.id}
        contentContainerStyle={{ padding: 12, paddingBottom: 8 }}
        renderItem={({ item }) => <Bubble msg={item} />}
        onContentSizeChange={scroll}
      />
      {busy ? (
        <View style={s.typing}>
          <ActivityIndicator color={theme.accent} size="small" />
          <Text style={s.typingText}>thinking…</Text>
        </View>
      ) : null}
      <View style={s.inputBar}>
        <TouchableOpacity style={s.micBtn} onPress={toggleListening} disabled={busy}>
          <Text style={[s.micText, recognizing && s.micActiveText]}>🎙</Text>
        </TouchableOpacity>
        <TextInput
          value={input}
          onChangeText={setInput}
          placeholder="Message your assistant…"
          placeholderTextColor={theme.textDim}
          style={s.input}
          multiline
          onSubmitEditing={send}
        />
        <TouchableOpacity style={s.sendBtn} onPress={send} disabled={busy || !input.trim()}>
          <Text style={s.sendText}>↑</Text>
        </TouchableOpacity>
      </View>
    </KeyboardAvoidingView>
  );
}

function Bubble({ msg }: { msg: Msg }) {
  const mine = msg.role === "user";
  return (
    <View style={[s.bubbleWrap, mine ? s.right : s.left]}>
      <View style={[s.bubble, mine ? s.bubbleMine : s.bubbleAI]}>
        <Text style={mine ? s.textMine : s.textAI}>{msg.text}</Text>
      </View>
      {msg.actions?.length ? (
        <Text style={s.meta}>✓ {msg.actions.join(" · ")}</Text>
      ) : null}
      {msg.proposals?.length ? (
        <Text style={s.proposal}>
          {msg.proposals.length} proposal{msg.proposals.length > 1 ? "s" : ""} awaiting your approval
          {" "}— review on the Agency console.
        </Text>
      ) : null}
    </View>
  );
}

const s = StyleSheet.create({
  wrap: { flex: 1, backgroundColor: theme.bg },
  bubbleWrap: { marginVertical: 5, maxWidth: "88%" },
  left: { alignSelf: "flex-start" },
  right: { alignSelf: "flex-end" },
  bubble: { borderRadius: 16, paddingHorizontal: 14, paddingVertical: 10, borderWidth: 1 },
  bubbleMine: { backgroundColor: theme.accent, borderColor: theme.accent, borderBottomRightRadius: 4 },
  bubbleAI: { backgroundColor: theme.card, borderColor: theme.border, borderBottomLeftRadius: 4 },
  textMine: { color: "#06122a", fontSize: 15, fontWeight: "600" },
  textAI: { color: theme.text, fontSize: 15, lineHeight: 21 },
  meta: { color: theme.good, fontSize: 12, marginTop: 4, marginLeft: 4 },
  proposal: { color: theme.watch, fontSize: 12, marginTop: 4, marginLeft: 4, lineHeight: 16 },
  typing: { flexDirection: "row", alignItems: "center", gap: 8, paddingHorizontal: 16, paddingBottom: 4 },
  typingText: { color: theme.textDim, fontSize: 12 },
  inputBar: {
    flexDirection: "row",
    alignItems: "flex-end",
    gap: 8,
    padding: 10,
    borderTopWidth: 1,
    borderTopColor: theme.border,
    backgroundColor: theme.card,
  },
  micBtn: {
    width: 40,
    height: 40,
    alignItems: "center",
    justifyContent: "center",
  },
  micText: { color: theme.textDim, fontSize: 24 },
  micActiveText: { color: theme.watch },
  input: {
    flex: 1,
    backgroundColor: theme.cardAlt,
    borderWidth: 1,
    borderColor: theme.border,
    borderRadius: 20,
    color: theme.text,
    paddingHorizontal: 14,
    paddingVertical: 10,
    fontSize: 15,
    maxHeight: 120,
  },
  sendBtn: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: theme.accent,
    alignItems: "center",
    justifyContent: "center",
  },
  sendText: { color: "#06122a", fontSize: 20, fontWeight: "900" },
});
