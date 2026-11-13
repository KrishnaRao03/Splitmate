import { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useFocusEffect } from '@react-navigation/native';
import { useCallback, useState } from 'react';
import { Alert, Pressable, Share, StyleSheet, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { api } from '@/api/client';
import { AppButton } from '@/components/AppButton';
import { AppText as Text } from '@/components/AppText';
import { BrandMark } from '@/components/BrandMark';
import { Card } from '@/components/Card';
import { QrCode } from '@/components/QrCode';
import { Screen } from '@/components/Screen';
import { TextField } from '@/components/TextField';
import { useAuth } from '@/state/AuthContext';
import { colors, radius, spacing } from '@/theme/colors';
import { typography } from '@/theme/typography';
import { formatDate } from '@/utils/dates';
import { passwordError as describePasswordError } from '@/utils/validation';
import type { ProfileQr, RewardsSummary, RootStackParamList } from '@/types';

type Props = NativeStackScreenProps<RootStackParamList, 'Profile'>;
type OpenSection = 'details' | 'password' | 'rewards' | 'qr' | 'invite';
type IconName = keyof typeof Ionicons.glyphMap;

export function ProfileScreen({ navigation }: Props) {
  const auth = useAuth();
  const [name, setName] = useState(auth.user?.name || '');
  const [email, setEmail] = useState(auth.user?.email || '');
  const [emailPassword, setEmailPassword] = useState('');
  const [interacEmail, setInteracEmail] = useState(auth.user?.interac_email || '');
  const [paypalUsername, setPaypalUsername] = useState(auth.user?.paypal_username || '');
  const [upiId, setUpiId] = useState(auth.user?.upi_id || '');
  const [phone, setPhone] = useState(auth.user?.phone || '');
  const [otp, setOtp] = useState('');
  const [verificationRequired, setVerificationRequired] = useState(false);
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [inviteEmail, setInviteEmail] = useState('');
  const [savingDetails, setSavingDetails] = useState(false);
  const [savingPassword, setSavingPassword] = useState(false);
  const [inviting, setInviting] = useState(false);
  const [rewards, setRewards] = useState<RewardsSummary | null>(null);
  const [rewardsLoading, setRewardsLoading] = useState(true);
  const [rewardsError, setRewardsError] = useState<string | null>(null);
  const [qr, setQr] = useState<ProfileQr | null>(null);
  const [qrError, setQrError] = useState<string | null>(null);
  const [openSection, setOpenSection] = useState<OpenSection | null>(null);

  const loadRewards = useCallback(async () => {
    try {
      const data = await api.rewards();
      setRewards(data);
      setRewardsError(null);
    } catch (error) {
      setRewardsError(error instanceof Error ? error.message : 'Could not load rewards.');
    } finally {
      setRewardsLoading(false);
    }
  }, []);

  const loadQr = useCallback(async () => {
    try {
      setQr(await api.profileQr());
      setQrError(null);
    } catch (error) {
      setQrError(error instanceof Error ? error.message : 'Could not load your QR code.');
    }
  }, []);

  useFocusEffect(useCallback(() => {
    loadRewards();
    loadQr();
  }, [loadRewards, loadQr]));

  async function shareContact() {
    if (!qr) {
      return;
    }
    try {
      await Share.share({ message: qr.payload, title: 'Splitmate contact' });
    } catch {
      // The share sheet was dismissed or is unavailable; nothing to undo.
    }
  }

  const emailChanged = email.trim().toLowerCase() !== (auth.user?.email || '').toLowerCase();

  async function saveDetails() {
    setSavingDetails(true);
    try {
      const result = await auth.updateProfile({
        name,
        email,
        currentPassword: emailChanged ? emailPassword : undefined,
        interac_email: interacEmail.trim(),
        paypal_username: paypalUsername.trim(),
        upi_id: upiId.trim(),
        phone: phone.trim()
      });
      setEmailPassword('');
      setVerificationRequired(result.verificationRequired);
      Alert.alert(
        'Profile updated',
        result.verificationRequired
          ? result.otpSent
            ? 'Enter the OTP sent to your new email.'
            : 'Your email changed, but the OTP email could not be sent. Use Resend OTP.'
          : 'Your account details are up to date.'
      );
    } catch (error) {
      Alert.alert('Could not update profile', error instanceof Error ? error.message : 'Try again.');
    } finally {
      setSavingDetails(false);
    }
  }

  async function verifyEmail() {
    try {
      await auth.verifyEmail(email, otp);
      setOtp('');
      setVerificationRequired(false);
      Alert.alert('Email verified', 'Your new email is ready to use.');
    } catch (error) {
      Alert.alert('Could not verify email', error instanceof Error ? error.message : 'Try again.');
    }
  }

  async function changePassword() {
    const problem = describePasswordError(newPassword);
    if (problem) {
      Alert.alert('Choose a stronger password', problem);
      return;
    }
    setSavingPassword(true);
    try {
      await auth.updatePassword(currentPassword, newPassword, confirmPassword);
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
      Alert.alert('Password updated', 'Your other devices were signed out. Use your new password to sign in there.');
    } catch (error) {
      Alert.alert('Could not update password', error instanceof Error ? error.message : 'Try again.');
    } finally {
      setSavingPassword(false);
    }
  }

  async function inviteFriend() {
    setInviting(true);
    try {
      const result = await api.inviteSplitmate(inviteEmail);
      setInviteEmail('');
      // The reply is the same whether or not the address already has an account (so it can't be used to look people up).
      Alert.alert('Invite sent', result.message);
    } catch (error) {
      Alert.alert('Could not invite friend', error instanceof Error ? error.message : 'Try again.');
    } finally {
      setInviting(false);
    }
  }

  function toggle(section: OpenSection) {
    setOpenSection(current => (current === section ? null : section));
  }

  // A tappable row that opens or closes one section, so only one form is open at a time.
  function sectionRow(section: OpenSection, icon: IconName, title: string, subtitle?: string) {
    const open = openSection === section;
    return (
      <Pressable onPress={() => toggle(section)} style={styles.navRow} accessibilityState={{ expanded: open }}>
        <Ionicons name={icon} size={20} color={colors.primary} />
        <View style={styles.identityMain}>
          <Text style={styles.navTitle}>{title}</Text>
          {subtitle ? <Text style={styles.status}>{subtitle}</Text> : null}
        </View>
        <Ionicons name={open ? 'chevron-up' : 'chevron-down'} size={18} color={colors.muted} />
      </Pressable>
    );
  }

  function linkRow(icon: IconName, title: string, onPress: () => void) {
    return (
      <Pressable onPress={onPress} style={styles.navRow}>
        <Ionicons name={icon} size={20} color={colors.primary} />
        <Text style={[styles.navTitle, styles.identityMain]}>{title}</Text>
        <Ionicons name="chevron-forward" size={18} color={colors.muted} />
      </Pressable>
    );
  }

  const planName = rewards?.membership_plan && rewards.membership_plan !== 'free' ? rewards.membership_plan : 'Free';

  return (
    <Screen>
      <Card style={styles.identity}>
        <BrandMark size={48} />
        <View style={styles.identityMain}>
          <Text style={styles.title}>{auth.user?.name}</Text>
          <Text style={styles.help}>{auth.user?.email}</Text>
          <Text style={styles.status}>{auth.user?.is_email_verified ? 'Verified account' : 'Verification pending'}</Text>
          {auth.user?.created_at ? <Text style={styles.help}>Joined {formatDate(auth.user.created_at)}</Text> : null}
        </View>
      </Card>

      <Text style={styles.groupLabel}>Account</Text>
      <Card style={styles.list}>
        {sectionRow('details', 'person-outline', 'Edit details', 'Name, email and how people pay you')}
        {openSection === 'details' ? (
          <View style={styles.panel}>
            <TextField label="Full name" value={name} onChangeText={setName} autoCapitalize="words" />
            <TextField label="Email" value={email} onChangeText={setEmail} keyboardType="email-address" autoCapitalize="none" />
            <TextField label="Phone number (optional)" value={phone} onChangeText={setPhone} keyboardType="phone-pad" placeholder="416 555 0123" />
            {emailChanged ? (
              <TextField label="Current password (needed to change email)" value={emailPassword} onChangeText={setEmailPassword} secureTextEntry />
            ) : null}
            <Text style={styles.subSectionTitle}>How people can pay you</Text>
            <Text style={styles.help}>Shown to members who owe you. Splitmate never handles the money.</Text>
            <TextField label="Interac e-Transfer email" value={interacEmail} onChangeText={setInteracEmail} keyboardType="email-address" autoCapitalize="none" />
            <TextField label="PayPal.Me username" value={paypalUsername} onChangeText={setPaypalUsername} autoCapitalize="none" />
            <TextField label="UPI ID" value={upiId} onChangeText={setUpiId} autoCapitalize="none" placeholder="name@bank" />
            <AppButton icon="save-outline" loading={savingDetails} onPress={saveDetails}>Save details</AppButton>
          </View>
        ) : null}
        {verificationRequired ? (
          <View style={styles.panel}>
            <Text style={styles.subSectionTitle}>Verify new email</Text>
            <TextField label="6-digit OTP" value={otp} onChangeText={setOtp} keyboardType="number-pad" maxLength={6} />
            <AppButton icon="checkmark-outline" onPress={verifyEmail}>Verify email</AppButton>
            <AppButton icon="refresh-outline" variant="outline" onPress={() => auth.resendOtp(email)}>Resend OTP</AppButton>
          </View>
        ) : null}
        <View style={styles.divider} />
        {sectionRow('password', 'key-outline', 'Change password')}
        {openSection === 'password' ? (
          <View style={styles.panel}>
            <TextField label="Current password" value={currentPassword} onChangeText={setCurrentPassword} secureTextEntry />
            <TextField
              label="New password"
              value={newPassword}
              onChangeText={setNewPassword}
              secureTextEntry
              error={newPassword ? describePasswordError(newPassword) : ''}
            />
            <TextField label="Confirm new password" value={confirmPassword} onChangeText={setConfirmPassword} secureTextEntry />
            <AppButton icon="key-outline" variant="outline" loading={savingPassword} onPress={changePassword}>Update password</AppButton>
          </View>
        ) : null}
      </Card>

      <Text style={styles.groupLabel}>Rewards & plan</Text>
      <Card style={styles.section}>
        {rewardsLoading ? (
          <Text style={styles.help}>Loading rewards...</Text>
        ) : rewardsError ? (
          <View style={styles.subSection}>
            <Text style={styles.help}>{rewardsError}</Text>
            <AppButton icon="refresh-outline" variant="outline" onPress={() => { setRewardsLoading(true); loadRewards(); }}>
              Try again
            </AppButton>
          </View>
        ) : rewards ? (
          <View style={styles.subSection}>
            <View style={styles.rewardsHeader}>
              <View>
                <Text style={styles.rewardsPoints}>{rewards.points} pts</Text>
                <Text style={styles.help}>
                  {rewards.membership_plan === 'free' ? 'Free plan' : rewards.membership_plan} - {rewards.membership_status}
                </Text>
              </View>
              <Text style={styles.rewardsPercent}>{rewards.progress.percent}%</Text>
            </View>

            <View style={styles.progressTrack}>
              <View
                style={[
                  styles.progressFill,
                  {
                    width: `${Math.min(100, Math.max(0, rewards.progress.percent))}%`,
                    backgroundColor: rewards.progress.redeemable ? colors.success : colors.primary
                  }
                ]}
              />
            </View>

            <Text style={styles.help}>
              {rewards.progress.remaining > 0
                ? `${rewards.progress.remaining} pts to ${rewards.progress.tier.label}`
                : `You've reached ${rewards.progress.tier.label}`}
            </Text>
            {rewards.progress.redeemable ? (
              <Text style={styles.status}>Reward available</Text>
            ) : null}
            <Text style={styles.help}>Earning points is paused for now. Points you already have are kept.</Text>

            {(rewards.tiers?.length || rewards.recent_transactions) ? (
              <Pressable onPress={() => toggle('rewards')} style={styles.inlineToggle}>
                <Text style={styles.status}>{openSection === 'rewards' ? 'Hide tiers and history' : 'Show tiers and history'}</Text>
                <Ionicons name={openSection === 'rewards' ? 'chevron-up' : 'chevron-down'} size={16} color={colors.primary} />
              </Pressable>
            ) : null}

            {openSection === 'rewards' && rewards.tiers?.length ? (
              <View style={styles.subSection}>
                <View style={styles.divider} />
                <Text style={styles.subSectionTitle}>Reward tiers</Text>
                {rewards.tiers.map(tier => (
                  <View key={tier.points} style={styles.rowBetween}>
                    <Text style={[styles.help, rewards.points >= tier.points && styles.reached]}>{tier.label}</Text>
                    <Text style={styles.status}>{tier.points.toLocaleString()} pts</Text>
                  </View>
                ))}
              </View>
            ) : null}

            {openSection === 'rewards' && rewards.recent_transactions ? (
              <View style={styles.subSection}>
                <View style={styles.divider} />
                <Text style={styles.subSectionTitle}>Recent points</Text>
                {rewards.recent_transactions.length ? rewards.recent_transactions.map(item => (
                  <View key={item.id} style={styles.rowBetween}>
                    <View style={styles.identityMain}>
                      <Text style={styles.help}>{item.note || 'Points earned'}</Text>
                      <Text style={styles.status}>{formatDate(item.created_at)}</Text>
                    </View>
                    <Text style={styles.points}>+{item.points}</Text>
                  </View>
                )) : <Text style={styles.help}>No points yet.</Text>}
              </View>
            ) : null}
          </View>
        ) : null}
        <View style={styles.divider} />
        {linkRow('star-outline', `Membership - ${planName} plan`, () => navigation.navigate('Membership'))}
      </Card>

      <Text style={styles.groupLabel}>Share</Text>
      <Card style={styles.list}>
        {sectionRow('qr', 'qr-code-outline', 'Profile QR', 'Friends scan it to get your name and email')}
        {openSection === 'qr' ? (
          <View style={[styles.panel, styles.centered]}>
            {qr ? (
              <>
                <QrCode rows={qr.rows} size={200} />
                <AppButton icon="share-outline" variant="outline" onPress={shareContact}>Share contact card</AppButton>
              </>
            ) : qrError ? (
              <AppButton icon="refresh-outline" variant="outline" onPress={loadQr}>Load QR code</AppButton>
            ) : (
              <Text style={styles.help}>Loading QR code...</Text>
            )}
          </View>
        ) : null}
        <View style={styles.divider} />
        {sectionRow('invite', 'person-add-outline', 'Invite a friend', 'Send a Splitmate invite by email')}
        {openSection === 'invite' ? (
          <View style={styles.panel}>
            <TextField label="Email" value={inviteEmail} onChangeText={setInviteEmail} keyboardType="email-address" autoCapitalize="none" />
            <AppButton icon="mail-outline" loading={inviting} onPress={inviteFriend}>Send invite</AppButton>
          </View>
        ) : null}
      </Card>

      <Text style={styles.groupLabel}>More</Text>
      <Card style={styles.list}>
        {linkRow('mail-open-outline', 'Group invites', () => navigation.navigate('Invites'))}
        <View style={styles.divider} />
        {linkRow('chatbubbles-outline', 'Help Chat', () => navigation.navigate('HelpChat'))}
        <View style={styles.divider} />
        {linkRow('settings-outline', 'App settings', () => navigation.navigate('Settings'))}
      </Card>

      <AppButton icon="log-out-outline" variant="danger" onPress={auth.signOut}>Sign out</AppButton>
    </Screen>
  );
}

const styles = StyleSheet.create({
  identity: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md
  },
  identityMain: {
    flex: 1,
    gap: 2
  },
  section: {
    gap: spacing.sm
  },
  groupLabel: {
    color: colors.secondary,
    ...typography.caption,
    textTransform: 'uppercase',
    marginTop: spacing.sm
  },
  list: {
    paddingVertical: spacing.xs
  },
  navRow: {
    minHeight: 48,
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md
  },
  navTitle: {
    color: colors.ink,
    ...typography.bodyStrong
  },
  panel: {
    gap: spacing.md,
    paddingTop: spacing.xs,
    paddingBottom: spacing.md
  },
  centered: {
    alignItems: 'center'
  },
  inlineToggle: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs
  },
  subSection: {
    gap: spacing.sm
  },
  divider: {
    height: 1,
    backgroundColor: colors.border,
    marginVertical: spacing.xs
  },
  title: {
    color: colors.ink,
    ...typography.h2
  },
  subSectionTitle: {
    color: colors.ink,
    ...typography.label
  },
  help: {
    color: colors.secondary,
    ...typography.body
  },
  status: {
    color: colors.primary,
    ...typography.caption
  },
  rowBetween: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: spacing.sm
  },
  reached: {
    color: colors.success
  },
  points: {
    color: colors.success,
    ...typography.bodyStrong
  },
  rewardsHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between'
  },
  rewardsPoints: {
    color: colors.ink,
    ...typography.h2
  },
  rewardsPercent: {
    color: colors.secondary,
    ...typography.bodyStrong
  },
  progressTrack: {
    height: 8,
    borderRadius: radius.pill,
    backgroundColor: colors.surfaceAlt,
    overflow: 'hidden'
  },
  progressFill: {
    height: '100%',
    borderRadius: radius.pill
  }
});
