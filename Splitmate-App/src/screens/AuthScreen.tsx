import { useState } from 'react';
import { Alert, Pressable, StyleSheet, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import type { ApiError } from '@/api/client';
import { AppButton } from '@/components/AppButton';
import { AppText as Text } from '@/components/AppText';
import { BrandMark } from '@/components/BrandMark';
import { Card } from '@/components/Card';
import { Screen } from '@/components/Screen';
import { TextField } from '@/components/TextField';
import { useAuth } from '@/state/AuthContext';
import { colors, radius, spacing } from '@/theme/colors';
import { typography } from '@/theme/typography';
import { emailError as describeEmailError, passwordError as describePasswordError } from '@/utils/validation';

type Mode = 'login' | 'register' | 'verify' | 'forgot';

const OTP_NOT_SENT = "We couldn't send the verification email. Wait a minute and tap Resend OTP.";

export function AuthScreen() {
  const auth = useAuth();
  const [mode, setMode] = useState<Mode>('login');
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [otp, setOtp] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [showConnection, setShowConnection] = useState(false);

  const emailError = email ? describeEmailError(email) : '';
  const newPasswordError = mode === 'register' && password ? describePasswordError(password) : '';
  const loginTabActive = mode === 'login' || mode === 'forgot';
  const registerTabActive = mode === 'register' || mode === 'verify';

  function switchMode(nextMode: Mode) {
    setError('');
    setNotice('');
    if (nextMode !== 'verify') {
      setOtp('');
    }
    if (nextMode !== 'register') {
      setConfirmPassword('');
      setShowConfirmPassword(false);
    }
    setShowPassword(false);
    setMode(nextMode);
  }

  function passwordToggle(isVisible: boolean, onPress: () => void, label: string) {
    return (
      <Pressable
        accessibilityLabel={label}
        accessibilityRole="button"
        hitSlop={8}
        onPress={onPress}
        style={styles.passwordToggle}
      >
        <Ionicons name={isVisible ? 'eye-off-outline' : 'eye-outline'} size={22} color={colors.primaryDark} />
      </Pressable>
    );
  }

  async function resendOtp() {
    setError('');
    setNotice('');
    try {
      if (await auth.resendOtp(email)) {
        setNotice('A new code is on its way. Check your inbox and spam folder.');
      } else {
        setError(OTP_NOT_SENT);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong.');
    }
  }

  async function submit() {
    setError('');
    setNotice('');
    const emailProblem = describeEmailError(email);
    if (emailProblem) {
      setError(emailProblem);
      return;
    }
    // Only new passwords must meet the rules; older accounts can still sign in with what they have.
    if (mode === 'register' && describePasswordError(password)) {
      setError(describePasswordError(password));
      return;
    }
    if (mode !== 'verify' && mode !== 'forgot' && !password) {
      setError('Enter your password.');
      return;
    }
    if (mode === 'register' && password !== confirmPassword) {
      setError('Passwords do not match.');
      return;
    }

    setLoading(true);
    try {
      if (mode === 'login') {
        await auth.signIn(email, password);
      } else if (mode === 'register') {
        const registered = await auth.register(name, email, password, confirmPassword);
        setEmail(registered.email);
        setPassword('');
        setConfirmPassword('');
        setMode('verify');
        // Shown on screen as well as in an alert: Alert.alert does nothing in the web build.
        if (registered.otpSent) {
          setNotice('Check your email and enter the 6-digit OTP to finish registration.');
          Alert.alert('Check your email', 'Enter the 6-digit OTP to finish registration.');
        } else {
          setError(OTP_NOT_SENT);
        }
      } else if (mode === 'forgot') {
        await auth.requestPasswordReset(email);
        setPassword('');
        switchMode('login');
        Alert.alert('Check your email', 'If an account exists for that email, password reset instructions were sent.');
      } else {
        await auth.verifyEmail(email, otp);
      }
    } catch (err) {
      if (mode === 'login' && (err as ApiError).status === 403 && /verification/i.test((err as Error).message)) {
        // Signed up but never verified: go to the code screen and send a fresh code.
        setPassword('');
        setMode('verify');
        await resendOtp();
        return;
      }
      setError(err instanceof Error ? err.message : 'Something went wrong.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <Screen contentStyle={styles.authContent}>
      <View style={styles.hero}>
        <BrandMark size={44} />
        <Text style={styles.title}>Splitmate</Text>
      </View>

      <Card>
        <Text style={styles.cardTitle}>{loginTabActive ? 'Welcome back' : 'Create your account'}</Text>

        <View style={styles.modeRow}>
          <Pressable accessibilityRole="button" onPress={() => switchMode('login')} style={[styles.modeButton, loginTabActive && styles.modeActive]}>
            <Text style={[styles.modeText, loginTabActive && styles.modeTextActive]}>Login</Text>
          </Pressable>
          <Pressable accessibilityRole="button" onPress={() => switchMode('register')} style={[styles.modeButton, registerTabActive && styles.modeActive]}>
            <Text style={[styles.modeText, registerTabActive && styles.modeTextActive]}>Register</Text>
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
        ) : mode === 'forgot' ? null : (
          <>
            <TextField
              label="Password"
              value={password}
              onChangeText={setPassword}
              error={newPasswordError}
              secureTextEntry={!showPassword}
              autoCapitalize="none"
              autoCorrect={false}
              right={passwordToggle(showPassword, () => setShowPassword(value => !value), showPassword ? 'Hide password' : 'Show password')}
            />
            {mode === 'register' ? (
              <TextField
                label="Confirm Password"
                value={confirmPassword}
                onChangeText={setConfirmPassword}
                secureTextEntry={!showConfirmPassword}
                autoCapitalize="none"
                autoCorrect={false}
                right={passwordToggle(
                  showConfirmPassword,
                  () => setShowConfirmPassword(value => !value),
                  showConfirmPassword ? 'Hide confirm password' : 'Show confirm password'
                )}
              />
            ) : null}
          </>
        )}
        {mode === 'login' ? (
          <Pressable accessibilityRole="button" onPress={() => switchMode('forgot')} style={styles.inlineAction}>
            <Text style={styles.inlineActionText}>Forgot password?</Text>
          </Pressable>
        ) : null}
        {notice ? <Text style={styles.notice}>{notice}</Text> : null}
        {error ? <Text style={styles.error}>{error}</Text> : null}
        <AppButton loading={loading} onPress={submit}>
          {mode === 'login' ? 'Sign In' : mode === 'register' ? 'Create Account' : mode === 'forgot' ? 'Send Reset Link' : 'Verify Email'}
        </AppButton>
        {mode === 'verify' ? (
          <AppButton icon="refresh-outline" variant="ghost" onPress={resendOtp}>
            Resend OTP
          </AppButton>
        ) : null}
        {mode === 'forgot' ? (
          <AppButton icon="arrow-back-outline" variant="ghost" onPress={() => switchMode('login')}>
            Back to Sign In
          </AppButton>
        ) : null}

        <Pressable
          accessibilityRole="button"
          accessibilityLabel={showConnection ? 'Hide connection settings' : 'Show connection settings'}
          onPress={() => setShowConnection(value => !value)}
          style={styles.advancedToggle}
        >
          <Ionicons name="settings-outline" size={16} color={colors.muted} />
          <Text style={styles.advancedToggleText}>Connection settings</Text>
          <Ionicons name={showConnection ? 'chevron-up' : 'chevron-down'} size={16} color={colors.muted} />
        </Pressable>
        {showConnection ? (
          <View style={styles.advancedBody}>
            <TextField label="API URL" value={auth.apiBaseUrl} onChangeText={auth.setApiBaseUrl} autoCapitalize="none" />
            <Text style={styles.help}>Use your computer LAN IP when testing on a physical phone.</Text>
          </View>
        ) : null}
      </Card>
    </Screen>
  );
}

const styles = StyleSheet.create({
  authContent: {
    maxWidth: 560
  },
  hero: {
    alignItems: 'center',
    gap: spacing.xs,
    paddingTop: spacing.lg
  },
  title: {
    color: colors.ink,
    ...typography.h1
  },
  cardTitle: {
    color: colors.ink,
    marginBottom: spacing.md,
    ...typography.h3
  },
  modeRow: {
    flexDirection: 'row',
    gap: spacing.xs,
    marginBottom: spacing.md,
    backgroundColor: colors.surfaceAlt,
    borderRadius: radius.md,
    padding: 4
  },
  modeButton: {
    flex: 1,
    alignItems: 'center',
    borderRadius: radius.sm,
    paddingVertical: 10,
    backgroundColor: 'transparent'
  },
  modeActive: {
    backgroundColor: colors.primary
  },
  modeText: {
    color: colors.secondary,
    ...typography.bodyStrong
  },
  modeTextActive: {
    color: colors.white
  },
  notice: {
    color: colors.primaryDark,
    fontSize: 14,
    lineHeight: 20
  },
  error: {
    color: colors.danger,
    ...typography.bodyStrong
  },
  inlineAction: {
    alignSelf: 'flex-end'
  },
  inlineActionText: {
    color: colors.primary,
    ...typography.bodyStrong
  },
  passwordToggle: {
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: 40,
    minWidth: 40
  },
  help: {
    color: colors.muted,
    ...typography.caption
  },
  advancedToggle: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.xs,
    marginTop: spacing.md,
    paddingVertical: spacing.xs
  },
  advancedToggleText: {
    color: colors.muted,
    ...typography.label
  },
  advancedBody: {
    gap: spacing.sm,
    marginTop: spacing.sm
  }
});
