import { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useEffect, useMemo, useState } from 'react';
import { Alert, Platform, Pressable, StyleSheet, TextInput, View } from 'react-native';
import { Icon } from '@/components/Icon';
import * as DocumentPicker from 'expo-document-picker';
import * as ImagePicker from 'expo-image-picker';

import { api } from '@/api/client';
import { AppButton } from '@/components/AppButton';
import { UpgradePrompt, isLimitReached } from '@/components/UpgradePrompt';
import { AppText as Text } from '@/components/AppText';
import { Card } from '@/components/Card';
import { ChoiceChips } from '@/components/ChoiceChips';
import { Screen } from '@/components/Screen';
import { SegmentedControl } from '@/components/SegmentedControl';
import { TextField } from '@/components/TextField';
import { useAuth } from '@/state/AuthContext';
import { colors, radius, spacing } from '@/theme/colors';
import { typography } from '@/theme/typography';
import type { Expense, GroupMember, RootStackParamList } from '@/types';
import { formatMoney, parseAmount } from '@/utils/money';
import { notify } from '@/state/UndoToast';

type Props = NativeStackScreenProps<RootStackParamList, 'AddExpense'>;
type SplitType = 'equal' | 'selected' | 'exact' | 'percentage';
// What the user picks. "Equally" covers both the server's 'equal' (everyone ticked) and 'selected' (some ticked).
type SplitMode = 'equal' | 'exact' | 'percentage';
type ScannedItem = { key: number; name: string; quantity: number; price: string; keep: boolean; isTax?: boolean };
type ReceiptFile = { uri: string; name: string; mimeType?: string; file?: File };

/**
 * Works out how an existing expense was split so the edit form can start from it:
 * equal across everyone -> "equal", equal across some people -> "selected",
 * anything else -> "exact" with each person's amount filled in.
 */
function describeSplit(expense: Expense, members: GroupMember[]) {
  const shares = expense.splits.filter(split => split.amount > 0);
  const near = (a: number, b: number) => Math.abs(a - b) <= 0.02;
  const isEven = shares.length > 0 && shares.every(split => near(split.amount, shares[0].amount));
  if (isEven && shares.length === members.length) {
    return { type: 'equal' as SplitType, ids: members.map(member => member.id), amounts: {} as Record<number, string> };
  }
  if (isEven) {
    return { type: 'selected' as SplitType, ids: shares.map(split => split.user_id), amounts: {} as Record<number, string> };
  }
  return {
    type: 'exact' as SplitType,
    ids: members.map(member => member.id),
    amounts: Object.fromEntries(shares.map(split => [split.user_id, split.amount.toFixed(2)])) as Record<number, string>
  };
}

export function AddExpenseScreen({ navigation, route }: Props) {
  const { categories, currentUserId, defaultSplit, expense, groupId, members } = route.params;
  const auth = useAuth();
  const currencyCode = route.params.currency || auth.currencyCode;
  const editing = Boolean(expense);
  const existing = useMemo(() => (expense ? describeSplit(expense, members) : null), [expense, members]);
  const [description, setDescription] = useState(expense?.description ?? '');
  const [amount, setAmount] = useState(expense ? expense.amount.toFixed(2) : '');
  // Blank saves as "General" on the server, and keeps every suggestion visible until you type.
  const [category, setCategory] = useState(expense?.category ?? '');
  const [paidById, setPaidById] = useState(expense?.paid_by_id ?? currentUserId);
  const [receiptUrl, setReceiptUrl] = useState(expense?.receipt_url ?? '');
  const [receipt, setReceipt] = useState<ReceiptFile | null>(null);
  const initialType: SplitType = existing?.type ?? defaultSplit.type;
  const [splitMode, setSplitMode] = useState<SplitMode>(initialType === 'selected' ? 'equal' : initialType);
  const [showMore, setShowMore] = useState(Boolean(expense?.receipt_url) || (editing && expense?.category !== 'General'));
  const [selectedIds, setSelectedIds] = useState(() => new Set(
    existing
      ? existing.ids
      : defaultSplit.type === 'selected' ? defaultSplit.member_ids.map(Number) : members.map(member => member.id)
  ));
  const [values, setValues] = useState<Record<number, string>>(() => existing
    ? existing.amounts
    : Object.fromEntries(
      Object.entries(defaultSplit.percentages).map(([memberId, value]) => [Number(memberId), value])
    ));
  const [saving, setSaving] = useState(false);
  const [scanUsage, setScanUsage] = useState('');
  const [scanLimit, setScanLimit] = useState('');
  const [scanning, setScanning] = useState(false);
  const [scannedItems, setScannedItems] = useState<ScannedItem[]>([]);
  const [merchant, setMerchant] = useState<string | null>(null);

  const activeMembers = useMemo(() => {
    if (splitMode === 'equal') {
      return members.filter(member => selectedIds.has(member.id));
    }
    return members;
  }, [members, selectedIds, splitMode]);
  const everyoneSelected = activeMembers.length === members.length;
  // The server's split type: equal across a subset of people is 'selected'.
  const splitType: SplitType = splitMode === 'equal' ? (everyoneSelected ? 'equal' : 'selected') : splitMode;

  function toggleMember(member: GroupMember) {
    const next = new Set(selectedIds);
    if (next.has(member.id)) {
      next.delete(member.id);
    } else {
      next.add(member.id);
    }
    setSelectedIds(next);
  }

  async function chooseReceipt() {
    const result = await DocumentPicker.getDocumentAsync({
      type: ['image/*', 'application/pdf'],
      copyToCacheDirectory: true,
      multiple: false
    });
    if (!result.canceled) {
      setReceipt(result.assets[0]);
    }
  }

  // The expense amount and description follow whichever scanned items are ticked.
  function applyItems(items: ScannedItem[], store: string | null) {
    setScannedItems(items);
    const kept = items.filter(item => item.keep);
    const total = kept.reduce((sum, item) => sum + (parseAmount(item.price) ?? 0), 0);
    setAmount(total.toFixed(2));
    const names = kept.filter(item => !item.isTax).map(item => item.name.trim()).filter(Boolean).join(', ');
    const text = store ? (names ? `${store}: ${names}` : store) : names;
    setDescription(text.length > 120 ? `${text.slice(0, 117)}...` : text);
  }

  function updateItem(key: number, change: Partial<ScannedItem>) {
    applyItems(scannedItems.map(item => (item.key === key ? { ...item, ...change } : item)), merchant);
  }

  function scanReceipt() {
    // Alert buttons don't show on web, so go straight to the file picker there.
    if (Platform.OS === 'web') {
      void scanFrom('library');
      return;
    }
    Alert.alert('Scan receipt', 'Take a photo of the receipt or pick one you already have.', [
      { text: 'Take photo', onPress: () => void scanFrom('camera') },
      { text: 'Choose from library', onPress: () => void scanFrom('library') },
      { text: 'Cancel', style: 'cancel' }
    ]);
  }

  async function scanFrom(source: 'camera' | 'library') {
    const permission = source === 'camera'
      ? await ImagePicker.requestCameraPermissionsAsync()
      : await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!permission.granted) {
      notify(
        source === 'camera' ? 'Camera access needed' : 'Photo access needed',
        `Allow Splitmate to use your ${source === 'camera' ? 'camera' : 'photos'} in your phone's settings to scan receipts.`
      );
      return;
    }
    // A slightly compressed photo keeps uploads well under the server's 5 MB limit.
    const options: ImagePicker.ImagePickerOptions = { mediaTypes: ['images'], quality: 0.7 };
    const result = source === 'camera'
      ? await ImagePicker.launchCameraAsync(options)
      : await ImagePicker.launchImageLibraryAsync(options);
    if (result.canceled) {
      return;
    }
    const asset = result.assets[0];
    const image: ReceiptFile = {
      uri: asset.uri,
      name: asset.fileName || 'receipt.jpg',
      mimeType: asset.mimeType || 'image/jpeg',
      file: asset.file
    };
    setScanning(true);
    try {
      setScanLimit('');
      const scan = await api.scanReceipt(image);
      setScanUsage(scan.usage?.limit != null ? `${scan.usage.remaining} of ${scan.usage.limit} free scans left this month.` : '');
      const items: ScannedItem[] = scan.items.map((item, index) => ({
        key: index, name: item.name, quantity: item.quantity, price: item.price.toFixed(2), keep: true
      }));
      if (scan.tax > 0) {
        items.push({ key: items.length, name: 'Tax', quantity: 1, price: scan.tax.toFixed(2), keep: true, isTax: true });
      }
      setReceipt(image);
      setMerchant(scan.merchant || null);
      applyItems(items, scan.merchant || null);
    } catch (error) {
      if (isLimitReached(error)) {
        setScanLimit((error as Error).message);
        return;
      }
      notify('Could not scan receipt', error instanceof Error ? error.message : 'Try again.');
    } finally {
      setScanning(false);
    }
  }

  useEffect(() => {
    if (editing) {
      navigation.setOptions({ title: 'Edit expense' });
    }
  }, [editing, navigation]);

  const parsedAmount = parseAmount(amount);
  const money = (value: number) => formatMoney(value, currencyCode);

  // Category is free text; built-in and previously used categories are offered as you type.
  const categorySuggestions = useMemo(() => {
    const typed = category.trim().toLowerCase();
    return categories
      .filter(item => item.toLowerCase() !== typed && (!typed || item.toLowerCase().includes(typed)))
      .slice(0, 12);
  }, [categories, category]);

  // Live running total for the exact / percentage splits.
  const splitTotal = useMemo(() => {
    if (splitMode === 'equal') {
      return 0;
    }
    return members.reduce((sum, member) => sum + (parseAmount(values[member.id] || '0') ?? 0), 0);
  }, [members, splitMode, values]);
  const splitTarget = splitMode === 'percentage' ? 100 : parsedAmount ?? 0;
  const splitRemaining = Math.round((splitTarget - splitTotal) * 100) / 100;
  const addsUp = Math.abs(splitRemaining) <= 0.009;
  const equalShare = parsedAmount && activeMembers.length ? parsedAmount / activeMembers.length : null;

  // One plain sentence describing the whole split, so nobody has to read the form to know what happens.
  const payerName = paidById === currentUserId ? 'You' : members.find(member => member.id === paidById)?.name ?? 'Someone';
  const paidPart = parsedAmount ? `${payerName} paid ${money(parsedAmount)}.` : `${payerName} paid.`;
  const peopleCount = `${activeMembers.length} ${activeMembers.length === 1 ? 'person' : 'people'}`;
  const splitSummary = splitMode === 'equal'
    ? `${paidPart} Split equally between ${everyoneSelected ? 'everyone' : peopleCount}${equalShare ? `, ${money(equalShare)} each` : ''}.`
    : `${paidPart} Split by ${splitMode === 'exact' ? 'exact amounts' : 'percentages'}.`;

  async function save() {
    if (!description.trim()) {
      notify('Missing description', 'Say what the expense was for.');
      return;
    }
    if (parsedAmount === null || parsedAmount <= 0) {
      notify('Check the amount', 'Enter an amount greater than zero, like 24.50.');
      return;
    }
    if (splitMode === 'equal' && !activeMembers.length) {
      notify('Choose people', 'Tick at least one person to split with.');
      return;
    }
    if (splitMode !== 'equal' && !addsUp) {
      notify(
        splitMode === 'exact' ? 'Amounts do not add up' : 'Percentages do not add up',
        splitMode === 'exact'
          ? `The exact amounts total ${formatMoney(splitTotal, currencyCode)} but the expense is ${formatMoney(parsedAmount, currencyCode)}.`
          : `The percentages total ${splitTotal}% — they need to add up to 100%.`
      );
      return;
    }

    setSaving(true);
    try {
      const payload: Record<string, unknown> = {
        description: description.trim(),
        amount: parsedAmount.toFixed(2),
        category,
        paid_by_id: paidById,
        receipt_url: receiptUrl,
        split_type: splitType
      };
      if (splitType === 'selected') {
        payload.split_user_ids = activeMembers.map(member => member.id);
      }
      if (splitType === 'exact') {
        payload.exact_amounts = Object.fromEntries(members.map(member => [member.id, values[member.id] || '0']));
      }
      if (splitType === 'percentage') {
        payload.percentages = Object.fromEntries(members.map(member => [member.id, values[member.id] || '0']));
      }

      const receiptUpload = receipt ? {
        uri: receipt.uri,
        name: receipt.name,
        mimeType: receipt.mimeType,
        file: receipt.file
      } : undefined;
      if (expense) {
        await api.updateExpense(expense.id, payload, receiptUpload);
      } else {
        await api.addExpense(groupId, payload, receiptUpload);
      }
      navigation.goBack();
    } catch (error) {
      notify(editing ? 'Could not save expense' : 'Could not add expense', error instanceof Error ? error.message : 'Try again.');
    } finally {
      setSaving(false);
    }
  }

  return (
    <Screen>
      {/* Step 1: what was it */}
      <Card style={styles.section}>
        <Text style={styles.step}>1. What was it?</Text>
        <TextField label="Amount" value={amount} onChangeText={setAmount} keyboardType="decimal-pad" placeholder="0.00" />
        <TextField label="Description" value={description} onChangeText={setDescription} placeholder="Dinner, rent, groceries" />
        <AppButton icon="scan-outline" variant="outline" loading={scanning} onPress={scanReceipt}>
          {scannedItems.length ? 'Scan a Different Receipt' : 'Scan a Receipt Instead'}
        </AppButton>
        {scanUsage ? <Text style={styles.helper}>{scanUsage}</Text> : null}
        {scanLimit ? <UpgradePrompt message={scanLimit} /> : null}
      </Card>

      {scannedItems.length ? (
        <Card style={styles.section}>
          <Text style={styles.title}>Receipt items</Text>
          {scannedItems.map(item => (
            <View key={item.key} style={styles.itemRow}>
              <Pressable
                accessibilityLabel={item.keep ? `Remove ${item.name} from split` : `Add ${item.name} to split`}
                onPress={() => updateItem(item.key, { keep: !item.keep })}
                hitSlop={8}
              >
                <Icon name={item.keep ? 'checkbox' : 'square-outline'} size={22} color={colors.primary} />
              </Pressable>
              {item.quantity > 1 ? <Text style={styles.itemQuantity}>{item.quantity}×</Text> : null}
              <TextInput
                style={[styles.itemInput, styles.itemName, !item.keep && styles.itemOff]}
                value={item.name}
                onChangeText={name => updateItem(item.key, { name })}
              />
              <TextInput
                style={[styles.itemInput, styles.itemPrice, !item.keep && styles.itemOff]}
                value={item.price}
                onChangeText={price => updateItem(item.key, { price })}
                keyboardType="decimal-pad"
              />
            </View>
          ))}
          <Text style={styles.helper}>
            {scannedItems.filter(item => item.keep).length} of {scannedItems.length} items kept - {money(parsedAmount ?? 0)}. Untick anything that isn't part of this split.
          </Text>
        </Card>
      ) : null}

      {/* Step 2: who paid, and who shares it */}
      <Card style={styles.section}>
        <Text style={styles.step}>2. Who paid, and who shares it?</Text>
        <View style={styles.summary}>
          <Icon name="people-outline" size={20} color={colors.primary} />
          <Text style={styles.summaryText}>{splitSummary}</Text>
        </View>
        <ChoiceChips label="Paid by" value={paidById} onChange={setPaidById} options={members.map(member => ({ label: member.id === currentUserId ? 'You' : member.name, value: member.id }))} />
        <SegmentedControl<SplitMode>
          value={splitMode}
          onChange={setSplitMode}
          options={[
            { label: 'Equally', value: 'equal' },
            { label: 'Exact', value: 'exact' },
            { label: 'Percent', value: 'percentage' }
          ]}
        />

        {splitMode === 'equal' ? (
          <View>
            {members.map(member => {
              const included = selectedIds.has(member.id);
              return (
                <Pressable
                  key={member.id}
                  onPress={() => toggleMember(member)}
                  style={styles.memberRow}
                  accessibilityRole="checkbox"
                  accessibilityState={{ checked: included }}
                >
                  <Icon name={included ? 'checkbox' : 'square-outline'} size={22} color={colors.primary} />
                  <Text style={[styles.memberName, !included && styles.memberOff]}>{member.id === currentUserId ? 'You' : member.name}</Text>
                  <Text style={[styles.memberShare, !included && styles.memberOff]}>
                    {included && equalShare ? money(equalShare) : included ? '' : 'Not included'}
                  </Text>
                </Pressable>
              );
            })}
            {!everyoneSelected ? (
              <Pressable onPress={() => setSelectedIds(new Set(members.map(member => member.id)))} hitSlop={8}>
                <Text style={styles.link}>Include everyone</Text>
              </Pressable>
            ) : null}
          </View>
        ) : (
          <View style={styles.section}>
            {members.map(member => (
              <TextField
                key={member.id}
                label={`${member.id === currentUserId ? 'You' : member.name}${splitMode === 'percentage' ? ' (%)' : ''}`}
                value={values[member.id] || ''}
                onChangeText={text => setValues(current => ({ ...current, [member.id]: text }))}
                keyboardType="decimal-pad"
                placeholder={splitMode === 'exact' ? '0.00' : '0'}
              />
            ))}
            <Text style={[styles.helper, addsUp ? styles.ok : styles.off]}>
              {addsUp
                ? 'Adds up perfectly.'
                : splitMode === 'exact'
                  ? `${money(Math.abs(splitRemaining))} ${splitRemaining > 0 ? 'left to assign' : 'over the total'}`
                  : `${Math.abs(splitRemaining)}% ${splitRemaining > 0 ? 'left to assign' : 'over 100%'}`}
            </Text>
          </View>
        )}
      </Card>

      {/* Step 3: optional extras, folded away so the main flow stays short */}
      <Card style={styles.section}>
        <Pressable style={styles.moreRow} onPress={() => setShowMore(open => !open)} accessibilityRole="button">
          <View style={styles.moreText}>
            <Text style={styles.step}>More options</Text>
            <Text style={styles.helper}>{category.trim() || 'General'}{receipt || receiptUrl ? ' - receipt attached' : ''}</Text>
          </View>
          <Icon name={showMore ? 'chevron-up' : 'chevron-down'} size={20} color={colors.primary} />
        </Pressable>
        {showMore ? (
          <>
            <TextField label="Category" value={category} onChangeText={setCategory} placeholder="Groceries, Pet supplies, Gym..." maxLength={40} />
            {categorySuggestions.length ? (
              <View style={styles.suggestions}>
                {categorySuggestions.map(item => (
                  <Pressable key={item} onPress={() => setCategory(item)} style={styles.suggestion} accessibilityRole="button" accessibilityLabel={`Use category ${item}`}>
                    <Text style={styles.suggestionText}>{item}</Text>
                  </Pressable>
                ))}
              </View>
            ) : null}
            <AppButton icon="attach-outline" variant="outline" onPress={chooseReceipt}>{receipt ? 'Change receipt file' : 'Attach Receipt (Image or PDF)'}</AppButton>
            {receipt ? <Text style={styles.helper}>{receipt.name}</Text> : null}
            <TextField label="Receipt link (optional)" value={receiptUrl} onChangeText={setReceiptUrl} autoCapitalize="none" placeholder="https://" />
          </>
        ) : null}
      </Card>

      <AppButton icon={editing ? 'save-outline' : 'add-outline'} loading={saving} onPress={save}>
        {`${editing ? 'Save changes' : 'Add expense'}${parsedAmount ? ` · ${money(parsedAmount)}` : ''}`}
      </AppButton>
    </Screen>
  );
}

const styles = StyleSheet.create({
  section: {
    gap: spacing.md
  },
  step: {
    color: colors.ink,
    ...typography.bodyStrong
  },
  summary: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    padding: spacing.md,
    borderRadius: radius.md,
    backgroundColor: colors.primarySoft
  },
  summaryText: {
    flex: 1,
    color: colors.ink,
    ...typography.body
  },
  title: {
    color: colors.ink,
    ...typography.h3
  },
  memberRow: {
    minHeight: 44,
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.border
  },
  itemRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm
  },
  itemInput: {
    minHeight: 40,
    paddingHorizontal: spacing.sm,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.sm,
    color: colors.text,
    ...typography.body
  },
  itemName: {
    flex: 1
  },
  itemPrice: {
    width: 84,
    textAlign: 'right'
  },
  itemQuantity: {
    color: colors.muted,
    ...typography.bodyStrong
  },
  itemOff: {
    color: colors.muted,
    textDecorationLine: 'line-through'
  },
  memberName: {
    flex: 1,
    color: colors.text,
    ...typography.bodyStrong
  },
  memberShare: {
    color: colors.text,
    ...typography.body
  },
  memberOff: {
    color: colors.muted
  },
  link: {
    color: colors.primary,
    paddingTop: spacing.sm,
    ...typography.bodyStrong
  },
  suggestions: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.sm
  },
  suggestion: {
    minHeight: 36,
    justifyContent: 'center',
    paddingHorizontal: spacing.md,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.primaryBorder,
    backgroundColor: colors.primarySoft
  },
  suggestionText: {
    color: colors.primary,
    ...typography.caption
  },
  moreRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm
  },
  moreText: {
    flex: 1
  },
  helper: {
    color: colors.muted,
    ...typography.caption
  },
  ok: {
    color: colors.success
  },
  off: {
    color: colors.danger
  }
});
