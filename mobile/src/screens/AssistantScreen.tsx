import React, { useCallback, useRef, useState } from "react";
import {
  View, Text, TextInput, TouchableOpacity, StyleSheet, FlatList,
  KeyboardAvoidingView, Platform, ActivityIndicator, Alert
} from "react-native";
import * as ImagePicker from "expo-image-picker";
import * as DocumentPicker from "expo-document-picker";
import { api, ApiError, ChatResult } from "../api";
import { theme } from "../theme";
import { listenOnce, speak, sttAvailable, stopListening, stopSpeaking, ttsAvailable } from "../voice";

type Msg = {
  id: string;
  role: "user" | "assistant";
  text: string;
  actions?: string[];
  proposals?: { id: string; title?: string }[];
};

let _seq = 0;
const nextId = () => `m${_seq++}`;

// Aadyon Assist: a conversational tab that can read AND write your data. It talks to
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
  const [listening, setListening] = useState(false);
  const [speakReplies, setSpeakReplies] = useState(false);
  const convId = useRef<string | undefined>(undefined);
  const listRef = useRef<FlatList<Msg>>(null);

  const scroll = () => setTimeout(() => listRef.current?.scrollToEnd({ animated: true }), 50);

  const send = useCallback(async () => {
    const text = input.trim();
    if (!text || busy) return;
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
      setMessages((m) => {
        const updated = m.map((msg) =>
          msg.id === botId
            ? { ...msg, actions: res.actions, proposals: res.proposals }
            : msg
        );
        if (speakReplies) {
          const reply = updated.find((msg) => msg.id === botId);
          if (reply?.text) speak(reply.text);
        }
        return updated;
      });
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : String(e);
      setMessages((m) => [...m, { id: nextId(), role: "assistant", text: `⚠️ ${msg}` }]);
    } finally {
      setBusy(false);
      scroll();
    }
  }, [input, busy, speakReplies]);

  const mic = useCallback(async () => {
    if (listening) {
      stopListening();
      return;
    }
    setListening(true);
    try {
      const heard = await listenOnce((partial) => setInput(partial));
      if (heard) setInput(heard);
    } finally {
      setListening(false);
    }
  }, [listening]);

  const uploadFile = async (uri: string, name: string, mimeType: string) => {
    setBusy(true);
    scroll();
    const botId = nextId();
    setMessages((m) => [...m, { id: botId, role: "assistant", text: "Uploading document..." }]);
    try {
      const res = await api.uploadDocument(uri, name, mimeType);
      setMessages((m) =>
        m.map((msg) =>
          msg.id === botId ? { ...msg, text: `✓ Document uploaded successfully! It has been queued for analysis and will appear in your Agency tab for review shortly.` } : msg
        )
      );
    } catch (e) {
      const err = e instanceof ApiError ? e.message : String(e);
      setMessages((m) =>
        m.map((msg) =>
          msg.id === botId ? { ...msg, text: `⚠️ Upload failed: ${err}` } : msg
        )
      );
    } finally {
      setBusy(false);
      scroll();
    }
  };

  // Wraps each picker so a denied permission or picker error surfaces as an
  // alert instead of an unhandled rejection (Alert onPress swallows those).
  const pickAndUpload = async (pick: () => Promise<void>) => {
    try {
      await pick();
    } catch (e) {
      Alert.alert("Upload", e instanceof Error ? e.message : String(e));
    }
  };

  const pickDocument = useCallback(() => {
    Alert.alert("Upload Document", "Choose a source to upload a document or receipt:", [
      { text: "Camera", onPress: () => pickAndUpload(async () => {
          const perm = await ImagePicker.requestCameraPermissionsAsync();
          if (!perm.granted) throw new Error("Camera access is needed to take a photo.");
          const res = await ImagePicker.launchCameraAsync({ quality: 0.8 });
          if (!res.canceled) uploadFile(res.assets[0].uri, res.assets[0].fileName || "photo.jpg", res.assets[0].mimeType || "image/jpeg");
      })},
      { text: "Photo Library", onPress: () => pickAndUpload(async () => {
          const perm = await ImagePicker.requestMediaLibraryPermissionsAsync();
          if (!perm.granted) throw new Error("Photo library access is needed to pick a photo.");
          const res = await ImagePicker.launchImageLibraryAsync({ quality: 0.8 });
          if (!res.canceled) uploadFile(res.assets[0].uri, res.assets[0].fileName || "photo.jpg", res.assets[0].mimeType || "image/jpeg");
      })},
      { text: "Files / PDF", onPress: () => pickAndUpload(async () => {
          const res = await DocumentPicker.getDocumentAsync({ type: ["application/pdf", "image/*"] });
          if (!res.canceled) uploadFile(res.assets[0].uri, res.assets[0].name, res.assets[0].mimeType || "application/pdf");
      })},
      { text: "Cancel", style: "cancel" }
    ]);
  }, []);

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
        {ttsAvailable() ? (
          <TouchableOpacity
            style={[s.voiceBtn, speakReplies && s.voiceBtnOn]}
            onPress={() => {
              if (speakReplies) stopSpeaking();
              setSpeakReplies(!speakReplies);
            }}
          >
            <Text style={s.voiceIcon}>{speakReplies ? "🔊" : "🔈"}</Text>
          </TouchableOpacity>
        ) : null}
        <TouchableOpacity style={s.plusBtn} onPress={pickDocument} disabled={busy}>
          <Text style={s.plusIcon}>+</Text>
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
        {sttAvailable() ? (
          <TouchableOpacity
            style={[s.voiceBtn, listening && s.voiceBtnLive]}
            onPress={mic}
            disabled={busy}
          >
            <Text style={s.voiceIcon}>{listening ? "⏹" : "🎤"}</Text>
          </TouchableOpacity>
        ) : null}
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
  voiceBtn: {
    width: 40, height: 40, borderRadius: 20, alignItems: "center", justifyContent: "center",
    borderWidth: 1, borderColor: theme.border, backgroundColor: theme.cardAlt,
  },
  voiceBtnOn: { borderColor: theme.accent },
  voiceBtnLive: { borderColor: theme.bad, backgroundColor: "#3a1520" },
  voiceIcon: { fontSize: 18 },
  plusBtn: {
    width: 36, height: 36, borderRadius: 18, alignItems: "center", justifyContent: "center",
    backgroundColor: theme.cardAlt, borderWidth: 1, borderColor: theme.border,
    marginRight: 4,
  },
  plusIcon: { fontSize: 24, color: theme.textDim, fontWeight: "400", marginTop: -2 },
});
