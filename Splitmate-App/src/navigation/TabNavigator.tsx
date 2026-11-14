import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { Icon, IconName } from '@/components/Icon';

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

const ICONS: Record<keyof MainTabParamList, IconName> = {
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
        tabBarActiveTintColor: accentColor,
        tabBarInactiveTintColor: colors.muted,
        tabBarStyle: { backgroundColor: colors.surface, borderTopColor: colors.border },
        tabBarIcon: ({ color, size }) => <Icon name={ICONS[route.name]} size={size} color={color} />
      })}
    >
      <Tab.Screen name="Home" component={HomeScreen} options={{ title: 'Splitmate', tabBarLabel: 'Home', headerTitle: () => <BrandLogo size={132} /> }} />
      <Tab.Screen name="Split" component={SplitScreen} options={{ title: 'Split' }} />
      <Tab.Screen name="Tasks" component={TasksScreen} options={{ title: 'Tasks' }} />
      <Tab.Screen name="Notes" component={NotesScreen} options={{ title: 'Notes' }} />
    </Tab.Navigator>
  );
}
