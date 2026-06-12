import { useState } from 'react';
import { Alert, Pressable, StyleSheet, Text, View } from 'react-native';

import { AppButton } from '@/components/AppButton';
import { Card } from '@/components/Card';
import { Screen } from '@/components/Screen';
import { TextField } from '@/components/TextField';
import { useAuth } from '@/state/AuthContext';
import { colors, spacing } from '@/theme/colors';

type Mode = 'login' | 'register' | 'verify';

const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function AuthScreen() {
  const auth = useAuth();
  const [mode, setMode] = useState<Mode>('login');
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [otp, setOtp] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const emailError = email && !emailPattern.test(email.trim()) ? 'Enter a valid email address.' : '';

  async function submit() {
    setError('');
    if (!emailPattern.test(email.trim())) {
      setError('Enter a valid email address.');
      return;
    }
    if (mode !== 'verify' && password.length < 6) {
      setError('Password must be at least 6 characters.');
      return;
    }

    setLoading(true);
    try {
      if (mode === 'login') {
        await auth.signIn(email, password);
      } else if (mode === 'register') {
        const registeredEmail = await auth.register(name, email, password);
        setEmail(registeredEmail);
        setMode('verify');
        Alert.alert('Check your email', 'Enter the 6-digit OTP to finish registration.');
      } else {
        await auth.verifyEmail(email, otp);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <Screen>
      <View style={styles.hero}>
        <View style={styles.logo}><Text style={styles.logoText}>S</Text></View>
        <Text style={styles.title}>Splitmate</Text>
        <Text style={styles.subtitle}>Shared expenses, tasks, notes, and reminders on your phone.</Text>
      </View>

      <Card>
        <View style={styles.modeRow}>
          <Pressable onPress={() => setMode('login')} style={[styles.modeButton, mode === 'login' && styles.modeActive]}>
            <Text style={[styles.modeText, mode === 'login' && styles.modeTextActive]}>Login</Text>
          </Pressable>
          <Pressable onPress={() => setMode('register')} style={[styles.modeButton, mode === 'register' && styles.modeActive]}>
            <Text style={[styles.modeText, mode === 'register' && styles.modeTextActive]}>Register</Text>
          </Pressable>
        </View>

        {mode === 'register' ? (
          <TextField label="Name" value={name} onChangeText={setName} autoCapitalize="words" />
        ) : null}
        <TextField
          label="Email"
          value={email}
          onChangeText={setEmail}
          autoCapitalize="none"
          autoCorrect={false}
          inputMode="email"
          keyboardType="email-address"
          error={emailError}
        />
        {mode === 'verify' ? (
          <TextField label="OTP" value={otp} onChangeText={setOtp} keyboardType="number-pad" maxLength={6} />
        ) : (
          <TextField label="Password" value={password} onChangeText={setPassword} secureTextEntry />
        )}
        {error ? <Text style={styles.error}>{error}</Text> : null}
        <AppButton loading={loading} onPress={submit}>
          {mode === 'login' ? 'Sign In' : mode === 'register' ? 'Create Account' : 'Verify Email'}
        </AppButton>
        {mode === 'verify' ? (
          <AppButton variant="ghost" onPress={() => auth.resendOtp(email).catch(err => setError(err.message))}>
            Resend OTP
          </AppButton>
        ) : null}
      </Card>

      <Card>
        <TextField label="API URL" value={auth.apiBaseUrl} onChangeText={auth.setApiBaseUrl} autoCapitalize="none" />
        <Text style={styles.help}>Use your computer LAN IP when testing on a physical phone.</Text>
      </Card>
    </Screen>
  );
}

const styles = StyleSheet.create({
  hero: {
    alignItems: 'center',
    gap: spacing.sm,
    paddingTop: spacing.xl
  },
  logo: {
    width: 64,
    height: 64,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 18,
    backgroundColor: colors.primary
  },
  logoText: {
    color: colors.white,
    fontSize: 28,
    fontWeight: '900'
  },
  title: {
    color: colors.ink,
    fontSize: 34,
    fontWeight: '900'
  },
  subtitle: {
    maxWidth: 320,
    color: colors.muted,
    textAlign: 'center',
    fontWeight: '700'
  },
  modeRow: {
    flexDirection: 'row',
    gap: spacing.xs,
    marginBottom: spacing.md
  },
  modeButton: {
    flex: 1,
    alignItems: 'center',
    borderRadius: 8,
    paddingVertical: 10,
    backgroundColor: colors.surfaceBlue
  },
  modeActive: {
    backgroundColor: colors.primary
  },
  modeText: {
    color: colors.primaryDark,
    fontWeight: '800'
  },
  modeTextActive: {
    color: colors.white
  },
  error: {
    color: colors.danger,
    fontWeight: '800'
  },
  help: {
    color: colors.muted,
    fontSize: 12,
    fontWeight: '700'
  }
});
