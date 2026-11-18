import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { StyleSheet, View } from 'react-native';

import { AppButton } from '@/components/AppButton';
import { AppText as Text } from '@/components/AppText';
import { Card } from '@/components/Card';
import { Icon } from '@/components/Icon';
import { Screen } from '@/components/Screen';
import { useAuth } from '@/state/AuthContext';
import { colors, radius, spacing } from '@/theme/colors';
import { typography } from '@/theme/typography';
import type { RootStackParamList } from '@/types';
import { formatMoney } from '@/utils/money';

type Props = NativeStackScreenProps<RootStackParamList, 'SplitRequested'>;

/** The end of "split a bill": shows who was asked for how much, and that it waits on them paying and you confirming. */
export function SplitRequestedScreen({ navigation, route }: Props) {
  const { currencyCode } = useAuth();
  const { expense, groupId, groupName } = route.params;
  const money = (value: number) => formatMoney(value, route.params.currency || currencyCode);
  const owing = expense.splits.filter(split => split.user_id !== expense.paid_by_id && split.amount > 0);
  const total = owing.reduce((sum, split) => sum + split.amount, 0);

  return (
    <Screen contentStyle={styles.content}>
      <Card style={styles.card}>
        <View style={styles.icon}>
          <Icon name="checkmark" size={28} color={colors.onHighlight} />
        </View>
        <Text style={styles.title}>Bill split</Text>
        <Text style={styles.body}>
          {expense.description} is added. Here's what each person owes you, {money(total)} in total. Nobody is asked to pay until you settle up.
        </Text>

        <View style={styles.list}>
          {owing.map(split => (
            <View key={split.id} style={styles.row}>
              <View style={styles.rowText}>
                <Text style={styles.name}>{split.user}</Text>
                <Text style={styles.amount}>{money(split.amount)}</Text>
              </View>
              <View style={[styles.pill, split.is_settled ? styles.pillDone : styles.pillWaiting]}>
                <Text style={[styles.pillText, split.is_settled && styles.pillTextDone]}>
                  {split.is_settled ? 'Settled' : 'Not settled yet'}
                </Text>
              </View>
            </View>
          ))}
        </View>

        <AppButton icon="people-outline" onPress={() => navigation.replace('GroupDetail', { groupId, groupName })}>Open {groupName}</AppButton>
        <AppButton icon="swap-horizontal-outline" variant="outline" onPress={() => navigation.replace('SettleUp', { groupId, groupName })}>Settle up now</AppButton>
        <AppButton variant="ghost" onPress={() => navigation.reset({ index: 0, routes: [{ name: 'Main' }] })}>Done</AppButton>
      </Card>
    </Screen>
  );
}

const styles = StyleSheet.create({
  content: {
    maxWidth: 520,
    justifyContent: 'center',
    flexGrow: 1
  },
  card: {
    alignItems: 'center',
    gap: spacing.md,
    paddingVertical: spacing.xl
  },
  icon: {
    width: 64,
    height: 64,
    borderRadius: 9999,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.highlight
  },
  title: {
    ...typography.h2,
    color: colors.ink,
    textAlign: 'center'
  },
  body: {
    ...typography.body,
    color: colors.secondary,
    textAlign: 'center'
  },
  list: {
    alignSelf: 'stretch',
    gap: spacing.sm
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    padding: spacing.md,
    borderRadius: radius.md,
    borderCurve: 'continuous',
    backgroundColor: colors.surfaceAlt
  },
  rowText: {
    flex: 1,
    gap: 2
  },
  name: {
    ...typography.bodyStrong,
    color: colors.ink
  },
  amount: {
    ...typography.caption,
    color: colors.muted
  },
  pill: {
    paddingHorizontal: spacing.sm,
    paddingVertical: 4,
    borderRadius: 9999
  },
  pillWaiting: {
    backgroundColor: colors.primarySoft
  },
  pillDone: {
    backgroundColor: colors.successSoft
  },
  pillText: {
    ...typography.caption,
    color: colors.ink
  },
  pillTextDone: {
    color: colors.success
  }
});
