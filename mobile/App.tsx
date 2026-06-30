import React from "react";
import { Text } from "react-native";
import { StatusBar } from "expo-status-bar";
import { NavigationContainer, DefaultTheme } from "@react-navigation/native";
import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";
import { SafeAreaProvider } from "react-native-safe-area-context";

import { theme } from "./src/theme";
import DigitalMeScreen from "./src/screens/DigitalMeScreen";
import TrackerScreen from "./src/screens/TrackerScreen";
import AgencyScreen from "./src/screens/AgencyScreen";
import SettingsScreen from "./src/screens/SettingsScreen";

const Tab = createBottomTabNavigator();

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

export default function App() {
  return (
    <SafeAreaProvider>
      <StatusBar style="light" />
      <NavigationContainer theme={navTheme}>
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
          <Tab.Screen name="Me" component={DigitalMeScreen} options={{ title: "Digital Me" }} />
          <Tab.Screen name="Tracker" component={TrackerScreen} />
          <Tab.Screen name="Org" component={AgencyScreen} options={{ title: "Agency" }} />
          <Tab.Screen name="Settings" component={SettingsScreen} />
        </Tab.Navigator>
      </NavigationContainer>
    </SafeAreaProvider>
  );
}
