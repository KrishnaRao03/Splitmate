import { useMemo, useState } from 'react';
import { FlatList, Modal, Pressable, StyleSheet, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { AppText as Text } from '@/components/AppText';
import { TextField } from '@/components/TextField';
import { colors, radius, spacing } from '@/theme/colors';
import { typography } from '@/theme/typography';
import { COUNTRIES, countryByCode } from '@/utils/countries';

type Props = {
  label?: string;
  value: string;
  onChange: (code: string) => void;
  hint?: string;
};

/** A field that opens a searchable country list. Shows each country's currency. */
export function CountryPicker({ label = 'Country', value, onChange, hint }: Props) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState('');
  const selected = countryByCode(value);
  const filtered = useMemo(() => {
    const query = search.trim().toLowerCase();
    return query
      ? COUNTRIES.filter(country => `${country.name} ${country.code} ${country.currency}`.toLowerCase().includes(query))
      : COUNTRIES;
  }, [search]);

  return (
    <View style={styles.wrap}>
      <Text style={styles.label}>{label}</Text>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={`${label}: ${selected ? selected.name : 'not chosen'}. Tap to change.`}
        onPress={() => setOpen(true)}
        style={styles.field}
      >
        <Text style={selected ? styles.value : styles.placeholder}>
          {selected ? `${selected.name} (${selected.currency})` : 'Choose your country'}
        </Text>
        <Ionicons name="chevron-down" size={18} color={colors.muted} />
      </Pressable>
      {hint ? <Text style={styles.hint}>{hint}</Text> : null}

      <Modal visible={open} transparent animationType="fade" onRequestClose={() => setOpen(false)}>
        <Pressable style={styles.backdrop} onPress={() => setOpen(false)}>
          <Pressable style={styles.sheet} onPress={() => undefined}>
            <View style={styles.sheetHeader}>
              <Text style={styles.sheetTitle}>Choose your country</Text>
              <Pressable accessibilityLabel="Close" onPress={() => setOpen(false)} hitSlop={8}>
                <Ionicons name="close" size={22} color={colors.secondary} />
              </Pressable>
            </View>
            <TextField label="Search" value={search} onChangeText={setSearch} placeholder="Canada, India, USD..." autoCorrect={false} />
            <FlatList
              data={filtered}
              keyExtractor={country => country.code}
              keyboardShouldPersistTaps="handled"
              style={styles.list}
              renderItem={({ item }) => (
                <Pressable
                  accessibilityRole="button"
                  onPress={() => {
                    onChange(item.code);
                    setSearch('');
                    setOpen(false);
                  }}
                  style={[styles.row, item.code === value && styles.rowSelected]}
                >
                  <Text style={styles.value}>{item.name}</Text>
                  <Text style={styles.currency}>{item.currency}</Text>
                </Pressable>
              )}
            />
          </Pressable>
        </Pressable>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    gap: spacing.xs
  },
  label: {
    color: colors.secondary,
    ...typography.label
  },
  field: {
    minHeight: 48,
    borderWidth: 1,
    borderColor: colors.borderStrong,
    borderRadius: radius.md,
    backgroundColor: colors.input,
    paddingHorizontal: spacing.md,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between'
  },
  value: {
    color: colors.text,
    ...typography.body
  },
  placeholder: {
    color: colors.placeholder,
    ...typography.body
  },
  hint: {
    color: colors.muted,
    ...typography.caption
  },
  backdrop: {
    flex: 1,
    backgroundColor: 'rgba(15, 23, 42, 0.45)',
    justifyContent: 'center',
    padding: spacing.md
  },
  sheet: {
    alignSelf: 'center',
    width: '100%',
    maxWidth: 480,
    maxHeight: '80%',
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    padding: spacing.md,
    gap: spacing.sm
  },
  sheetHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between'
  },
  sheetTitle: {
    color: colors.ink,
    ...typography.h3
  },
  list: {
    flexGrow: 0
  },
  row: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.sm,
    borderRadius: radius.md
  },
  rowSelected: {
    backgroundColor: colors.primarySoft
  },
  currency: {
    color: colors.muted,
    ...typography.body
  }
});
