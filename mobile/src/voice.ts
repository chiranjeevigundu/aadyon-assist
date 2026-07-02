// Voice layer for the assistant: speech-to-text (expo-speech-recognition) and
// text-to-speech (expo-speech). Modules are loaded lazily so the app still runs
// in environments without the native STT module (e.g. plain Expo Go) — the mic
// simply hides. Build with `eas build` (dev/preview) to get full voice.
let Speech: any = null;
try {
  Speech = require("expo-speech");
} catch {}

let STT: any = null;
try {
  STT = require("expo-speech-recognition");
} catch {}

export const ttsAvailable = () => !!Speech;
export const sttAvailable = () => !!STT?.ExpoSpeechRecognitionModule;

export function speak(text: string) {
  if (!Speech || !text) return;
  Speech.stop();
  // Strip markdown-ish noise so it reads naturally.
  Speech.speak(text.replace(/[*_`#>-]/g, " ").replace(/\s+/g, " ").trim(), {
    language: "en-US",
    rate: 1.0,
  });
}

export function stopSpeaking() {
  Speech?.stop();
}

/** Start one dictation session; resolves with the final transcript ("" if none). */
export async function listenOnce(onPartial?: (text: string) => void): Promise<string> {
  if (!sttAvailable()) return "";
  const mod = STT.ExpoSpeechRecognitionModule;
  const perms = await mod.requestPermissionsAsync();
  if (!perms.granted) return "";

  return new Promise<string>((resolve) => {
    let finalText = "";
    const subs: { remove(): void }[] = [];
    const done = () => {
      subs.forEach((s) => s.remove());
      resolve(finalText.trim());
    };
    subs.push(STT.addSpeechRecognitionListener("result", (e: any) => {
      const t = e?.results?.[0]?.transcript ?? "";
      if (t) {
        finalText = t;
        onPartial?.(t);
      }
    }));
    subs.push(STT.addSpeechRecognitionListener("end", done));
    subs.push(STT.addSpeechRecognitionListener("error", done));
    mod.start({ lang: "en-US", interimResults: true, continuous: false });
  });
}

export function stopListening() {
  STT?.ExpoSpeechRecognitionModule?.stop();
}
