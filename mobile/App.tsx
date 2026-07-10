import React, { useEffect, useState } from "react";
import { Text, View } from "react-native";
import { StatusBar } from "expo-status-bar";
import { NavigationContainer, DefaultTheme } from "@react-navigation/native";
import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import { SafeAreaProvider } from "react-native-safe-area-context";

import { theme } from "./src/theme";
import { getToken, setUnauthorizedHandler } from "./src/api";
import { Loading } from "./src/components";
import LoginScreen from "./src/screens/LoginScreen";
import AssistantScreen from "./src/screens/AssistantScreen";
import DigitalMeScreen from "./src/screens/DigitalMeScreen";
import TrackerScreen from "./src/screens/TrackerScreen";
import AgencyScreen from "./src/screens/AgencyScreen";
import SettingsScreen from "./src/screens/SettingsScreen";
import MailScreen from "./src/screens/MailScreen";

const Tab = createBottomTabNavigator();
const SettingsStack = createNativeStackNavigator();

const navTheme = {
  ...DefaultTheme,
  colors: {
    ...DefaultTheme.colors,
    background: theme.bg,
    card: theme.card,
    text: theme.text,
    border: theme.border,
    primary: theme.accent,
  },
};

// Simple emoji tab icons — no icon font dependency needed.
const ICONS: Record<string, string> = {
  Assistant: "💬",
  Me: "🧭",
  Tracker: "📋",
  Org: "🤖",
  Settings: "⚙️",
};

function tabIcon(name: string) {
  return ({ focused }: { focused: boolean }) => (
    <Text style={{ fontSize: 20, opacity: focused ? 1 : 0.5 }}>{ICONS[name]}</Text>
  );
}

// Settings hosts sub-pages (mail integrations now, more connectors later),
// so it's a stack with its own header/back button; the tab header is hidden.
function SettingsStackScreen({ onLogout }: { onLogout: () => void }) {
  return (
    <SettingsStack.Navigator
      screenOptions={{
        headerStyle: { backgroundColor: theme.bg },
        headerTitleStyle: { color: theme.text, fontWeight: "800" },
        headerTintColor: theme.accent,
        headerShadowVisible: false,
      }}
    >
      <SettingsStack.Screen name="SettingsHome" options={{ title: "Settings" }}>
        {({ navigation }) => (
          <SettingsScreen onLogout={onLogout} onOpenMail={() => navigation.navigate("Mail")} />
        )}
      </SettingsStack.Screen>
      <SettingsStack.Screen name="Mail" component={MailScreen} options={{ title: "Email accounts" }} />
    </SettingsStack.Navigator>
  );
}

function Tabs({ onLogout }: { onLogout: () => void }) {
  return (
    <Tab.Navigator
      screenOptions={({ route }) => ({
        headerStyle: { backgroundColor: theme.bg },
        headerTitleStyle: { color: theme.text, fontWeight: "800" },
        headerShadowVisible: false,
        tabBarStyle: { backgroundColor: theme.card, borderTopColor: theme.border },
        tabBarActiveTintColor: theme.accent,
        tabBarInactiveTintColor: theme.textDim,
        tabBarIcon: tabIcon(route.name),
      })}
    >
      <Tab.Screen name="Assistant" component={AssistantScreen} options={{ title: "Assistant" }} />
      <Tab.Screen name="Me" component={DigitalMeScreen} options={{ title: "Digital Me" }} />
      <Tab.Screen name="Tracker" component={TrackerScreen} />
      <Tab.Screen name="Org" component={AgencyScreen} options={{ title: "Agency" }} />
      <Tab.Screen name="Settings" options={{ title: "Settings", headerShown: false }}>
        {() => <SettingsStackScreen onLogout={onLogout} />}
      </Tab.Screen>
    </Tab.Navigator>
  );
}

export default function App() {
  const [authed, setAuthed] = useState<boolean | null>(null); // null = still checking

  useEffect(() => {
    getToken().then((t) => setAuthed(!!t));
    // A 401 from anywhere drops us back to the login screen.
    setUnauthorizedHandler(() => setAuthed(false));
    return () => setUnauthorizedHandler(null);
  }, []);

  return (
    <SafeAreaProvider>
      <StatusBar style="light" />
      {authed === null ? (
        <View style={{ flex: 1, backgroundColor: theme.bg }}>
          <Loading label="Starting…" />
        </View>
      ) : authed ? (
        <NavigationContainer theme={navTheme}>
          <Tabs onLogout={() => setAuthed(false)} />
        </NavigationContainer>
      ) : (
        <LoginScreen onAuthed={() => setAuthed(true)} />
      )}
    </SafeAreaProvider>
  );
}
