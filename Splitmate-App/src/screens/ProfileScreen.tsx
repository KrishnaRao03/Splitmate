import { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useFocusEffect } from '@react-navigation/native';
import { useCallback, useState } from 'react';
import { Pressable, Share, StyleSheet, View } from 'react-native';
import { Icon, IconName } from '@/components/Icon';

import { api } from '@/api/client';
import { AppButton } from '@/components/AppButton';
import { AppText as Text } from '@/components/AppText';
import { BrandMark } from '@/components/BrandMark';
import { Card } from '@/components/Card';
import { QrCode } from '@/components/QrCode';
import { Screen } from '@/components/Screen';
import { TextField } from '@/components/TextField';
import { useAuth } from '@/state/AuthContext';
import { colors, spacing } from '@/theme/colors';
import { typography } from '@/theme/typography';
import { CountryPicker } from '@/components/CountryPicker';
import { paymentFieldsFor } from '@/utils/countries';
import { formatDate } from '@/utils/dates';
import { passwordError as describePasswordError } from '@/utils/validation';
import { notify } from '@/state/UndoToast';
import type { ProfileQr, RewardsSummary, RootStackParamList } from '@/types';

type Props = NativeStackScreenProps<RootStackParamList, 'Profile'>;
type OpenSection = 'details' | 'password' | 'rewards' | 'qr' | 'invite';

export function ProfileScreen({ navigation }: Props) {
  const auth = useAuth();
  const [name, setName] = useState(auth.user?.name || '');
  const [email, setEmail] = useState(auth.user?.email || '');
  const [emailPassword, setEmailPassword] = useState('');
  const [interacEmail, setInteracEmail] = useState(auth.user?.interac_email || '');
  const [paypalUsername, setPaypalUsername] = useState(auth.user?.paypal_username || '');
  const [upiId, setUpiId] = useState(auth.user?.upi_id || '');
  const [country, setCountry] = useState(auth.user?.country || 'CA');
  const [phone, setPhone] = useState(auth.user?.phone || '');
  const [otp, setOtp] = useState('');
  const [interacOtp, setInteracOtp] = useState('');
  const [interacMessage, setInteracMessage] = useState<string | null>(null);
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

  const [redeeming, setRedeeming] = useState<string | null>(null);

  async function redeemReward(rewardId: string, label: string) {
    setRedeeming(rewardId);
    try {
      setRewards(await api.redeemReward(rewardId));
      notify('Reward added', label);
    } catch (error) {
      notify('Could not get reward', error instanceof Error ? error.message : undefined);
    } finally {
      setRedeeming(null);
    }
  }

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
      await Share.share({ message: `Add me on Splitmate: ${qr.payload}`, title: 'Add me on Splitmate' });
    } catch {
      // The share sheet was dismissed or is unavailable; nothing to undo.
    }
  }

  const emailChanged = email.trim().toLowerCase() !== (auth.user?.email || '').toLowerCase();
  const countryChanged = country !== (auth.user?.country || 'CA');
  // Only the payment apps that work in the chosen country are offered (PayPal works everywhere).
  const paymentFields = paymentFieldsFor(country);
  const typedInterac = interacEmail.trim().toLowerCase();
  const paymentChanged =
    (typedInterac !== (auth.user?.interac_email || '').toLowerCase() && typedInterac !== (auth.user?.pending_interac_email || '').toLowerCase())
    || paypalUsername.trim() !== (auth.user?.paypal_username || '')
    || upiId.trim() !== (auth.user?.upi_id || '');
  const pendingInterac = auth.user?.pending_interac_email || '';

  async function saveDetails() {
    setSavingDetails(true);
    try {
      const result = await auth.updateProfile({
        name,
        email,
        currentPassword: emailChanged || paymentChanged || countryChanged ? emailPassword : undefined,
        country,
        interac_email: paymentFields.includes('interac_email') ? interacEmail.trim() : undefined,
        paypal_username: paypalUsername.trim(),
        upi_id: paymentFields.includes('upi_id') ? upiId.trim() : undefined,
        phone: phone.trim()
      });
      setEmailPassword('');
      setVerificationRequired(result.verificationRequired);
      if (result.interacCodeSent) {
        setInteracMessage('We emailed a 6-digit code to your new Interac email. Enter it below to start using it.');
      }
      notify(
        'Profile updated',
        result.verificationRequired
          ? result.otpSent
            ? 'Enter the OTP sent to your new email.'
            : 'Your email changed, but the OTP email could not be sent. Use Resend OTP.'
          : 'Your account details are up to date.'
      );
    } catch (error) {
      notify('Could not update profile', error instanceof Error ? error.message : 'Try again.');
      setInteracMessage(error instanceof Error ? error.message : 'Could not update profile.');
    } finally {
      setSavingDetails(false);
    }
  }

  async function verifyEmail() {
    try {
      await auth.verifyEmail(email, otp);
      setOtp('');
      setVerificationRequired(false);
      notify('Email verified', 'Your new email is ready to use.');
    } catch (error) {
      notify('Could not verify email', error instanceof Error ? error.message : 'Try again.');
    }
  }

  async function verifyInterac() {
    try {
      await api.verifyInterac(interacOtp.trim());
      await auth.reloadUser();
      setInteracOtp('');
      setInteracMessage('Interac email confirmed. Members who owe you can now see it.');
    } catch (error) {
      setInteracMessage(error instanceof Error ? error.message : 'Could not check the code. Try again.');
    }
  }

  async function resendInteracCode() {
    try {
      const result = await api.resendInteracCode();
      setInteracMessage(result.sent ? 'A new code is on its way.' : 'The code email could not be sent. Try again in a minute.');
    } catch (error) {
      setInteracMessage(error instanceof Error ? error.message : 'Could not resend the code.');
    }
  }

  async function changePassword() {
    const problem = describePasswordError(newPassword);
    if (problem) {
      notify('Choose a stronger password', problem);
      return;
    }
    setSavingPassword(true);
    try {
      await auth.updatePassword(currentPassword, newPassword, confirmPassword);
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
      notify('Password updated', 'Your other devices were signed out. Use your new password to sign in there.');
    } catch (error) {
      notify('Could not update password', error instanceof Error ? error.message : 'Try again.');
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
      notify('Invite sent', result.message);
    } catch (error) {
      notify('Could not invite friend', error instanceof Error ? error.message : 'Try again.');
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
        <Icon name={icon} size={20} color={colors.primary} />
        <View style={styles.identityMain}>
          <Text style={styles.navTitle}>{title}</Text>
          {subtitle ? <Text style={styles.status}>{subtitle}</Text> : null}
        </View>
        <Icon name={open ? 'chevron-up' : 'chevron-down'} size={18} color={colors.muted} />
      </Pressable>
    );
  }

  function linkRow(icon: IconName, title: string, onPress: () => void) {
    return (
      <Pressable onPress={onPress} style={styles.navRow}>
        <Icon name={icon} size={20} color={colors.primary} />
        <Text style={[styles.navTitle, styles.identityMain]}>{title}</Text>
        <Icon name="chevron-forward" size={18} color={colors.muted} />
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
            <CountryPicker value={country} onChange={setCountry} hint="Sets your currency and which payment apps you can add. Changing it needs your password." />
            <Text style={styles.subSectionTitle}>How people can pay you</Text>
            <Text style={styles.help}>Shown to members who owe you. Splitmate never handles the money. Changes need your password and we email you about them.</Text>
            {paymentFields.includes('interac_email') ? (
            <>
            <TextField label="Interac e-Transfer email" value={interacEmail} onChangeText={setInteracEmail} keyboardType="email-address" autoCapitalize="none" />
            {auth.user?.interac_email ? (
              <Text style={styles.status}>
                {auth.user.interac_email_verified ? `Verified: ${auth.user.interac_email}` : `Not verified yet: ${auth.user.interac_email} (hidden from others)`}
              </Text>
            ) : null}
            {pendingInterac ? (
              <View style={styles.panel}>
                <Text style={styles.help}>Waiting for the code sent to {pendingInterac}. Others keep seeing your old Interac email until you enter it.</Text>
                <TextField label="Interac code" value={interacOtp} onChangeText={setInteracOtp} keyboardType="number-pad" maxLength={6} />
                <AppButton icon="checkmark-outline" onPress={verifyInterac}>Confirm Interac email</AppButton>
                <AppButton icon="refresh-outline" variant="outline" onPress={resendInteracCode}>Resend code</AppButton>
              </View>
            ) : null}
            {interacMessage ? <Text style={styles.help}>{interacMessage}</Text> : null}
            </>
            ) : null}
            <TextField label="PayPal.Me username" value={paypalUsername} onChangeText={setPaypalUsername} autoCapitalize="none" />
            {paymentFields.includes('upi_id') ? (
              <TextField label="UPI ID" value={upiId} onChangeText={setUpiId} autoCapitalize="none" placeholder="name@bank" />
            ) : null}
            {emailChanged || paymentChanged || countryChanged ? (
              <TextField label="Current password (needed for these changes)" value={emailPassword} onChangeText={setEmailPassword} secureTextEntry />
            ) : null}
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
                  {rewards.membership_plan === 'free' ? 'Free plan' : rewards.membership_plan} · {rewards.membership_status}
                </Text>
              </View>
            </View>

            {rewards.points_pro_until ? (
              <Text style={styles.status}>Pro from points until {formatDate(rewards.points_pro_until)}</Text>
            ) : null}
            {rewards.bonus_receipt_scans || rewards.bonus_grocery_compares ? (
              <Text style={styles.help}>
                Extra: {rewards.bonus_receipt_scans} receipt scans, {rewards.bonus_grocery_compares} grocery comparisons
              </Text>
            ) : null}
            <Text style={styles.help}>Spend points on Pro time and extra scans. Points have no cash value.</Text>

            {rewards.rewards.map(reward => (
              <View key={reward.id} style={styles.rowBetween}>
                <View style={styles.identityMain}>
                  <Text style={[styles.help, reward.affordable && styles.reached]}>{reward.label}</Text>
                  <Text style={styles.status}>{reward.points.toLocaleString()} pts</Text>
                </View>
                <AppButton
                  variant={reward.affordable ? 'primary' : 'outline'}
                  disabled={!reward.affordable || redeeming !== null}
                  loading={redeeming === reward.id}
                  onPress={() => redeemReward(reward.id, reward.label)}
                >
                  Get
                </AppButton>
              </View>
            ))}

            <Pressable onPress={() => toggle('rewards')} style={styles.inlineToggle}>
              <Text style={styles.status}>{openSection === 'rewards' ? 'Hide how to earn and history' : 'How to earn points'}</Text>
              <Icon name={openSection === 'rewards' ? 'chevron-up' : 'chevron-down'} size={16} color={colors.primary} />
            </Pressable>

            {openSection === 'rewards' ? (
              <View style={styles.subSection}>
                <View style={styles.divider} />
                <Text style={styles.subSectionTitle}>How to earn</Text>
                {rewards.ways_to_earn.map(way => (
                  <View key={way.label} style={styles.rowBetween}>
                    <View style={styles.identityMain}>
                      <Text style={styles.help}>{way.label}</Text>
                      <Text style={styles.status}>{way.limit}</Text>
                    </View>
                    <Text style={styles.points}>+{way.points}</Text>
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
                    <Text style={styles.points}>{item.points > 0 ? '+' : ''}{item.points}</Text>
                  </View>
                )) : <Text style={styles.help}>No points yet.</Text>}
              </View>
            ) : null}
          </View>
        ) : null}
        <View style={styles.divider} />
        {linkRow('star-outline', `Membership · ${planName} plan`, () => navigation.navigate('Membership'))}
      </Card>

      <Text style={styles.groupLabel}>Share</Text>
      <Card style={styles.list}>
        {sectionRow('qr', 'qr-code-outline', 'Profile QR', 'Friends scan it with their camera to add you')}
        {openSection === 'qr' ? (
          <View style={[styles.panel, styles.centered]}>
            {qr ? (
              <>
                <QrCode rows={qr.rows} size={200} />
                <AppButton icon="share-outline" variant="outline" onPress={shareContact}>Share my add link</AppButton>
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
        {linkRow('chatbubbles-outline', 'Help chat', () => navigation.navigate('HelpChat'))}
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
  }
});
