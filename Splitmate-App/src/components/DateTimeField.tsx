import DateTimePicker, { DateTimePickerAndroid } from '@react-native-community/datetimepicker';
import { useState } from 'react';
import { Platform, Pressable, StyleSheet, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { AppText as Text } from '@/components/AppText';
import { TextField } from '@/components/TextField';
import { colors, radius, spacing } from '@/theme/colors';
import { typography } from '@/theme/typography';
import { parseLocalInput } from '@/utils/dates';

type Props = {
  label: string;
  value: Date | null;
  onChange: (value: Date) => void;
  minimumDate?: Date;
};

function pad(value: number) {
  return String(value).padStart(2, '0');
}

function toInputText(value: Date | null) {
  return value
    ? `${value.getFullYear()}-${pad(value.getMonth() + 1)}-${pad(value.getDate())} ${pad(value.getHours())}:${pad(value.getMinutes())}`
    : '';
}

/** Date + time picker: native dialogs on Android, the inline compact picker on iOS, typed text on web. */
export function DateTimeField({ label, value, onChange, minimumDate }: Props) {
  const [webText, setWebText] = useState(toInputText(value));

  if (Platform.OS === 'web') {
    return (
      <TextField
        label={label}
        value={webText}
        placeholder="2026-06-15 18:00"
        onChangeText={text => {
          setWebText(text);
          const parsed = parseLocalInput(text);
          if (parsed) {
            onChange(parsed);
          }
        }}
      />
    );
  }

  if (Platform.OS === 'ios') {
    return (
      <View style={styles.field}>
        <Text style={styles.label}>{label}</Text>
        <DateTimePicker
          value={value ?? new Date()}
          mode="datetime"
          display="compact"
          minimumDate={minimumDate}
          onChange={(_, date) => date && onChange(date)}
        />
      </View>
    );
  }

  // Android has separate date and time dialogs: pick the day, then the time.
  function openAndroid() {
    const start = value ?? new Date();
    DateTimePickerAndroid.open({
      value: start,
      mode: 'date',
      minimumDate,
      onChange: (event, date) => {
        if (event.type !== 'set' || !date) {
          return;
        }
        DateTimePickerAndroid.open({
          value: start,
          mode: 'time',
          onChange: (timeEvent, time) => {
            if (timeEvent.type !== 'set' || !time) {
              return;
            }
            onChange(new Date(date.getFullYear(), date.getMonth(), date.getDate(), time.getHours(), time.getMinutes()));
          }
        });
      }
    });
  }

  return (
    <View style={styles.field}>
      <Text style={styles.label}>{label}</Text>
      <Pressable style={styles.button} onPress={openAndroid} accessibilityRole="button" accessibilityLabel={`${label}: ${value ? value.toLocaleString() : 'not set'}`}>
        <Ionicons name="calendar-outline" size={20} color={colors.primary} />
        <Text style={value ? styles.value : styles.placeholder}>
          {value ? value.toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' }) : 'Pick a date and time'}
        </Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  field: {
    gap: spacing.xs
  },
  label: {
    color: colors.ink,
    ...typography.label
  },
  button: {
    minHeight: 48,
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    paddingHorizontal: spacing.md,
    borderWidth: 1,
    borderColor: colors.borderStrong,
    borderRadius: radius.md,
    backgroundColor: colors.input
  },
  value: {
    color: colors.text,
    ...typography.body
  },
  placeholder: {
    color: colors.placeholder,
    ...typography.body
  }
});
