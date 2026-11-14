import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { Ionicons } from '@expo/vector-icons';

import { BrandLogo } from '@/components/BrandMark';
import { HeaderProfileButton } from '@/components/HeaderProfileButton';
import { HomeScreen } from '@/screens/HomeScreen';
import { NotesScreen } from '@/screens/NotesScreen';
import { SplitScreen } from '@/screens/SplitScreen';
import { TasksScreen } from '@/screens/TasksScreen';
import { useTheme } from '@/state/ThemeContext';
import { colors, fonts } from '@/theme/colors';
import type { MainTabParamList } from '@/types';

const Tab = createBottomTabNavigator<MainTabParamList>();

const ICONS: Record<keyof MainTabParamList, keyof typeof Ionicons.glyphMap> = {
  Home: 'home-outline',
  Split: 'cash-outline',
  Tasks: 'checkbox-outline',
  Notes: 'document-text-outline'
};

export function TabNavigator() {
  const { accentColor } = useTheme();
  return (
    <Tab.Navigator
      screenOptions={({ route }) => ({
        headerStyle: { backgroundColor: colors.surfaceGlass },
        headerShadowVisible: false,
        headerTintColor: colors.ink,
        headerTitleStyle: { fontFamily: fonts.extraBold, fontWeight: 'normal' },
        headerLeft: () => <HeaderProfileButton />,
        headerTitle: () => <BrandLogo size={150} />,
        headerTitleAlign: 'center',
        tabBarActiveTintColor: accentColor,
        tabBarInactiveTintColor: colors.muted,
        tabBarStyle: { backgroundColor: colors.surface, borderTopColor: colors.border },
        tabBarIcon: ({ color, size }) => <Ionicons name={ICONS[route.name]} size={size} color={color} />
      })}
    >
      <Tab.Screen name="Home" component={HomeScreen} options={{ title: 'Splitmate', tabBarLabel: 'Home' }} />
      <Tab.Screen name="Split" component={SplitScreen} options={{ title: 'Split' }} />
      <Tab.Screen name="Tasks" component={TasksScreen} options={{ title: 'Tasks' }} />
      <Tab.Screen name="Notes" component={NotesScreen} options={{ title: 'Notes' }} />
    </Tab.Navigator>
  );
}
