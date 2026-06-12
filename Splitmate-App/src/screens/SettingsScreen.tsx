import { useState } from 'react';
import { Alert, StyleSheet, Text } from 'react-native';

import { AppButton } from '@/components/AppButton';
import { Card } from '@/components/Card';
import { Screen } from '@/components/Screen';
import { TextField } from '@/components/TextField';
import { configureNotifications } from '@/services/notifications';
import { useAuth } from '@/state/AuthContext';
import { colors, spacing } from '@/theme/colors';

export function SettingsScreen() {
  const auth = useAuth();
  const [apiUrl, setApiUrl] = useState(auth.apiBaseUrl);

  async function enableNotifications() {
    const result = await configureNotifications();
    Alert.alert(
      result.granted ? 'Notifications ready' : 'Notifications disabled',
      result.token ? 'This device is registered for push notifications.' : 'Local task reminders will work when permission is granted.'
    );
  }

  return (
    <Screen>
      <Card>
        <Text style={styles.title}>Connection</Text>
        <TextField label="Mobile API URL" value={apiUrl} onChangeText={setApiUrl} autoCapitalize="none" />
        <AppButton onPress={() => auth.setApiBaseUrl(apiUrl)}>Save API URL</AppButton>
        <Text style={styles.help}>Example: http://192.168.1.20:5000/api/mobile</Text>
      </Card>

      <Card>
        <Text style={styles.title}>Notifications</Text>
        <Text style={styles.help}>Splitmate schedules local task reminders and registers the device token for future server push notifications.</Text>
        <AppButton variant="outline" onPress={enableNotifications}>Enable Notifications</AppButton>
      </Card>

      <Card>
        <Text style={styles.title}>{auth.user?.name}</Text>
        <Text style={styles.help}>{auth.user?.email}</Text>
        <AppButton variant="danger" onPress={auth.signOut}>Sign Out</AppButton>
      </Card>
    </Screen>
  );
}

const styles = StyleSheet.create({
  title: {
    color: colors.ink,
    fontSize: 18,
    fontWeight: '900',
    marginBottom: spacing.sm
  },
  help: {
    color: colors.muted,
    fontWeight: '700',
    marginBottom: spacing.md
  }
});
