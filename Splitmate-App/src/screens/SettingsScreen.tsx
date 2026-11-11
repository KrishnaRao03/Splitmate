import { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useFocusEffect } from '@react-navigation/native';
import Constants from 'expo-constants';
import { useCallback, useState } from 'react';
import { Alert, DevSettings, Pressable, Share, StyleSheet, Switch, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { api } from '@/api/client';
import { AppButton } from '@/components/AppButton';
import { AppText as Text } from '@/components/AppText';
import { Card } from '@/components/Card';
import { Screen } from '@/components/Screen';
import { SegmentedControl } from '@/components/SegmentedControl';
import { TextField } from '@/components/TextField';
import {
  NotificationPermission,
  configureNotifications,
  notificationPermissionStatus,
  setTaskNotificationsEnabled,
  taskNotificationsEnabled
} from '@/services/notifications';
import { useAuth } from '@/state/AuthContext';
import { ACCENT_PRESETS, AccentKey, ThemeMode, useTheme } from '@/state/ThemeContext';
import { colors, radius, spacing } from '@/theme/colors';
import { typography } from '@/theme/typography';
import type { RootStackParamList } from '@/types';

type Props = NativeStackScreenProps<RootStackParamList, 'Settings'>;

export function SettingsScreen({ navigation }: Props) {
  const auth = useAuth();
  const theme = useTheme();
  const [apiUrl, setApiUrl] = useState(auth.apiBaseUrl);
  const [exporting, setExporting] = useState(false);
  const [remindersOn, setRemindersOn] = useState(taskNotificationsEnabled);
  const [permission, setPermission] = useState<NotificationPermission>('not asked');

  const refreshPermission = useCallback(() => {
    notificationPermissionStatus().then(setPermission).catch(() => undefined);
  }, []);

  useFocusEffect(refreshPermission);

  async function enableNotifications() {
    const result = await configureNotifications();
    refreshPermission();
    Alert.alert(
      result.granted ? 'Notifications ready' : 'Notifications disabled',
      result.granted
        ? result.token ? 'This device is registered for push notifications.' : 'Task reminders will show on this device.'
        : 'Allow notifications for Splitmate in your phone settings to get task reminders.'
    );
  }

  async function toggleReminders(next: boolean) {
    setRemindersOn(next);
    await setTaskNotificationsEnabled(next).catch(() => undefined);
    if (next && permission !== 'allowed' && permission !== 'not supported') {
      await enableNotifications();
    }
  }

  function restartToApply() {
    if (__DEV__) {
      DevSettings.reload();
      return;
    }
    Alert.alert('Restart Splitmate', 'Close and reopen Splitmate to apply your new theme everywhere.');
  }

  async function exportMyData() {
    setExporting(true);
    try {
      const data = await api.exportData();
      await Share.share({ message: JSON.stringify(data, null, 2) });
    } catch (error) {
      Alert.alert('Could not export data', error instanceof Error ? error.message : 'Try again.');
    } finally {
      setExporting(false);
    }
  }

  return (
    <Screen>
      <Card style={styles.section}>
        <Text style={styles.title}>Connection</Text>
        <TextField label="Mobile API URL" value={apiUrl} onChangeText={setApiUrl} autoCapitalize="none" />
        <AppButton icon="save-outline" onPress={() => auth.setApiBaseUrl(apiUrl)}>Save API URL</AppButton>
        <Text style={styles.help}>Example: http://192.168.1.20:5000/api/mobile</Text>
      </Card>

      <Card style={styles.section}>
        <Text style={styles.title}>Theme</Text>
        <SegmentedControl<ThemeMode>
          value={theme.mode}
          onChange={theme.setMode}
          options={[
            { label: 'System', value: 'system' },
            { label: 'Light', value: 'light' },
            { label: 'Dark', value: 'dark' }
          ]}
        />
        <Text style={styles.help}>Accent color</Text>
        <View style={styles.swatchRow}>
          {(Object.keys(ACCENT_PRESETS) as AccentKey[]).map(key => {
            const preset = ACCENT_PRESETS[key];
            const active = theme.accent === key;
            return (
              <Pressable
                key={key}
                accessibilityLabel={`${preset.label} theme`}
                onPress={() => theme.setAccent(key)}
                style={styles.swatchItem}
              >
                <View style={[styles.swatch, { backgroundColor: preset.color }, active && styles.swatchActive]}>
                  {active ? <Ionicons name="checkmark" size={18} color={colors.white} /> : null}
                </View>
                <Text style={styles.swatchLabel}>{preset.label}</Text>
              </Pressable>
            );
          })}
        </View>
        {theme.restartNeeded ? (
          <View style={styles.restartRow}>
            <Text style={styles.help}>Restart Splitmate to apply your theme on every screen.</Text>
            <AppButton icon="refresh-outline" variant="outline" onPress={restartToApply}>Restart now</AppButton>
          </View>
        ) : null}
      </Card>

      <Card style={styles.section}>
        <Text style={styles.title}>Notifications</Text>
        <View style={styles.switchRow}>
          <View style={styles.switchText}>
            <Text style={styles.label}>Task notifications</Text>
            <Text style={styles.help}>Remind me on this phone when a task's reminder time arrives.</Text>
          </View>
          <Switch
            value={remindersOn}
            onValueChange={toggleReminders}
            disabled={permission === 'not supported'}
            trackColor={{ true: theme.accentColor, false: colors.borderStrong }}
            thumbColor={colors.white}
          />
        </View>
        <Text style={styles.help}>Permission: {permission === 'allowed' ? 'Allowed' : permission === 'blocked' ? 'Blocked in phone settings' : permission === 'not supported' ? 'Not supported here' : 'Not asked yet'}</Text>
        {permission !== 'allowed' && permission !== 'not supported' ? (
          <AppButton icon="notifications-outline" variant="outline" onPress={enableNotifications}>Allow notifications</AppButton>
        ) : null}
      </Card>

      <Card style={styles.section}>
        <Text style={styles.title}>Help</Text>
        <Text style={styles.help}>Quick answers about invites, splits, tasks, notes, points and more.</Text>
        <AppButton icon="chatbubbles-outline" variant="outline" onPress={() => navigation.navigate('HelpChat')}>Open Help Chat</AppButton>
      </Card>

      <Card style={styles.section}>
        <Text style={styles.title}>Your Data</Text>
        <Text style={styles.help}>Download a copy of your profile, groups, expenses, payments, tasks, notes and rewards as JSON.</Text>
        <AppButton icon="download-outline" variant="outline" loading={exporting} onPress={exportMyData}>Export my data</AppButton>
      </Card>

      <Card style={styles.section}>
        <Text style={styles.title}>{auth.user?.name}</Text>
        <Text style={styles.help}>{auth.user?.email}</Text>
        <AppButton icon="log-out-outline" variant="danger" onPress={auth.signOut}>Sign out</AppButton>
        <AppButton
          icon="phone-portrait-outline"
          variant="outline"
          onPress={() => Alert.alert('Sign out everywhere?', 'This signs you out of every phone and browser, including this one.', [
            { text: 'Cancel', style: 'cancel' },
            {
              text: 'Sign out everywhere',
              style: 'destructive',
              onPress: () => auth.signOutEverywhere().catch(error => Alert.alert('Could not sign out everywhere', error instanceof Error ? error.message : 'Try again.'))
            }
          ])}
        >
          Sign out of all devices
        </AppButton>
      </Card>

      <Text style={styles.version}>Splitmate {Constants.expoConfig?.version || ''} (Launch Prep)</Text>
    </Screen>
  );
}

const styles = StyleSheet.create({
  section: {
    gap: spacing.sm
  },
  title: {
    color: colors.ink,
    ...typography.h3,
    marginBottom: spacing.xs
  },
  help: {
    color: colors.secondary,
    ...typography.body
  },
  label: {
    color: colors.ink,
    ...typography.bodyStrong
  },
  switchRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md
  },
  switchText: {
    flex: 1,
    gap: 2
  },
  restartRow: {
    gap: spacing.sm,
    marginTop: spacing.xs
  },
  version: {
    color: colors.muted,
    ...typography.caption,
    textAlign: 'center'
  },
  swatchRow: {
    flexDirection: 'row',
    gap: spacing.md,
    marginTop: spacing.xs
  },
  swatchItem: {
    alignItems: 'center',
    gap: spacing.xs
  },
  swatch: {
    width: 40,
    height: 40,
    borderRadius: radius.pill,
    alignItems: 'center',
    justifyContent: 'center'
  },
  swatchActive: {
    borderWidth: 2,
    borderColor: colors.ink
  },
  swatchLabel: {
    ...typography.caption,
    color: colors.secondary
  }
});
