import { Pressable, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';

import { colors } from '@/theme/colors';
import type { RootStackParamList } from '@/types';

/**
 * Top-left header button shown on every tab screen; opens the Profile stack screen.
 * Uses the navigation hook (rather than a prop) so it works from any tab screen
 * nested inside the root stack's Main route without prop-drilling stack typings.
 */
export function HeaderProfileButton() {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  return (
    <Pressable accessibilityLabel="Profile" style={styles.button} onPress={() => navigation.navigate('Profile')}>
      <Ionicons name="person-outline" size={22} color={colors.primaryDark} />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  button: {
    width: 40,
    height: 40,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 12,
    backgroundColor: colors.surfaceBlue,
    marginLeft: 12
  }
});
