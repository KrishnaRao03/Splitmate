import { useState } from 'react';
import { Linking, Pressable, StyleSheet, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { AppText as Text } from '@/components/AppText';
import { colors, spacing } from '@/theme/colors';
import { typography } from '@/theme/typography';
import type { GroceryComparison } from '@/types';
import { formatMoney } from '@/utils/money';

/** Store-by-store prices for a grocery note; tap a store to see each item. Used on the group and Notes screens. */
export function GroceryComparisonView({ comparison }: { comparison: GroceryComparison }) {
  const [expandedStores, setExpandedStores] = useState<Record<number, boolean>>({});

  return (
    <View style={styles.comparison}>
      <Text style={styles.cardLabel}>Best Grocery Match</Text>
      {comparison.top_store ? (
        <Text style={styles.memberLine}>{comparison.top_store.store_name}: {formatMoney(comparison.top_store.total ?? 0, comparison.currency)}</Text>
      ) : null}
      {comparison.stores.map(store => {
        const open = expandedStores[store.rank];
        return (
          <View key={store.rank} style={styles.storeBlock}>
            <Pressable
              accessibilityRole="button"
              accessibilityLabel={`${open ? 'Hide' : 'Show'} items at ${store.store_name}`}
              onPress={() => setExpandedStores(current => ({ ...current, [store.rank]: !current[store.rank] }))}
              style={styles.rowBetween}
            >
              <View style={styles.headerText}>
                <Text style={styles.muted}>#{store.rank} {store.store_name}{store.all_items_available ? ' - has everything' : ''}</Text>
                <Text style={styles.memberLine}>
                  {store.available_count} in stock
                  {store.unavailable_count ? `, ${store.unavailable_count} out of stock` : ''}
                  {store.missing_count ? `, ${store.missing_count} not found` : ''}
                </Text>
              </View>
              <Text style={styles.amountNeutral}>{formatMoney(store.total, comparison.currency)}</Text>
              {store.items?.length ? <Ionicons name={open ? 'chevron-up' : 'chevron-down'} size={18} color={colors.muted} /> : null}
            </Pressable>
            {open && store.items ? store.items.map((line, index) => (
              <View key={`${store.rank}-${index}`} style={styles.groceryLine}>
                <Ionicons
                  name={line.status === 'available' ? 'checkmark-circle' : line.status === 'unavailable' ? 'remove-circle' : 'help-circle'}
                  size={16}
                  color={line.status === 'available' ? colors.success : line.status === 'unavailable' ? colors.warning : colors.muted}
                />
                <View style={styles.headerText}>
                  <Text style={styles.memberLine}>
                    {line.requested.quantity && line.requested.quantity > 1 ? `${line.requested.quantity} x ` : ''}{line.requested.name || line.requested.raw}
                  </Text>
                  <Text style={styles.groceryMatch}>
                    {line.status === 'missing'
                      ? 'Not found'
                      : `${line.matched_item || ''}${line.size ? ` (${line.size})` : ''}${line.status === 'unavailable' ? ' - out of stock' : ''}`}
                  </Text>
                  {line.source === 'web' && line.status !== 'missing' ? (
                    <Text
                      style={[styles.groceryMatch, line.source_url ? styles.sourceLink : null]}
                      onPress={line.source_url ? () => Linking.openURL(line.source_url as string) : undefined}
                    >
                      Online price{line.source_url ? ' - view' : ''}
                    </Text>
                  ) : null}
                </View>
                {line.status === 'available' ? <Text style={styles.memberLine}>{formatMoney(line.line_total, comparison.currency)}</Text> : null}
              </View>
            )) : null}
          </View>
        );
      })}
      {comparison.catalog_source ? <Text style={styles.groceryMatch}>Prices: {comparison.catalog_source}</Text> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  sourceLink: {
    color: colors.primary,
    textDecorationLine: 'underline'
  },
  comparison: {
    gap: spacing.sm,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    marginTop: spacing.md,
    paddingTop: spacing.md
  },
  cardLabel: {
    ...typography.label,
    color: colors.ink,
    marginBottom: spacing.sm
  },
  storeBlock: {
    gap: spacing.xs,
    paddingVertical: spacing.xs
  },
  rowBetween: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: spacing.md
  },
  headerText: {
    flex: 1
  },
  muted: {
    ...typography.caption,
    color: colors.muted
  },
  memberLine: {
    ...typography.caption,
    color: colors.secondary,
    marginTop: spacing.xs
  },
  amountNeutral: {
    ...typography.bodyStrong,
    color: colors.ink
  },
  groceryLine: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    paddingLeft: spacing.sm
  },
  groceryMatch: {
    color: colors.muted,
    ...typography.caption
  }
});
