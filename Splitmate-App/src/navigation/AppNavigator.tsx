import { createNativeStackNavigator } from '@react-navigation/native-stack';

import { colors, fonts } from '@/theme/colors';
import type { RootStackParamList } from '@/types';
import { useAuth } from '@/state/AuthContext';
import { LoadingState } from '@/components/States';
import { AddExpenseScreen } from '@/screens/AddExpenseScreen';
import { QuickSplitScreen } from '@/screens/QuickSplitScreen';
import { AddTaskScreen } from '@/screens/AddTaskScreen';
import { AuthScreen } from '@/screens/AuthScreen';
import { CreateGroupScreen } from '@/screens/CreateGroupScreen';
import { GroupsScreen } from '@/screens/GroupsScreen';
import { HelpChatScreen } from '@/screens/HelpChatScreen';
import { GroupDetailScreen } from '@/screens/GroupDetailScreen';
import { GroupSettingsScreen } from '@/screens/GroupSettingsScreen';
import { InsightsScreen } from '@/screens/InsightsScreen';
import { InvitesScreen } from '@/screens/InvitesScreen';
import { MembershipScreen } from '@/screens/MembershipScreen';
import { ProfileScreen } from '@/screens/ProfileScreen';
import { SettingsScreen } from '@/screens/SettingsScreen';
import { TaskCalendarScreen } from '@/screens/TaskCalendarScreen';
import { TabNavigator } from '@/navigation/TabNavigator';

const Stack = createNativeStackNavigator<RootStackParamList>();

export function AppNavigator() {
  const { isLoading, token } = useAuth();

  if (isLoading) {
    return <LoadingState />;
  }

  return (
    <Stack.Navigator
      screenOptions={{
        headerStyle: { backgroundColor: colors.surfaceGlass },
        headerShadowVisible: false,
        headerTintColor: colors.ink,
        headerTitleStyle: { fontFamily: fonts.extraBold, fontWeight: 'normal' },
        contentStyle: { backgroundColor: colors.bg }
      }}
    >
      {!token ? (
        <Stack.Screen name="Auth" component={AuthScreen} options={{ headerShown: false }} />
      ) : (
        <>
          <Stack.Screen name="Main" component={TabNavigator} options={{ headerShown: false }} />
          <Stack.Screen name="Groups" component={GroupsScreen} options={{ title: 'Your groups' }} />
          <Stack.Screen name="CreateGroup" component={CreateGroupScreen} options={{ title: 'Create group' }} />
          <Stack.Screen name="GroupDetail" component={GroupDetailScreen} options={({ route }) => ({ title: route.params.groupName })} />
          <Stack.Screen name="AddExpense" component={AddExpenseScreen} options={{ title: 'Add expense' }} />
          <Stack.Screen name="QuickSplit" component={QuickSplitScreen} options={{ title: 'Quick split' }} />
          <Stack.Screen name="AddTask" component={AddTaskScreen} options={{ title: 'Add task' }} />
          <Stack.Screen name="Profile" component={ProfileScreen} options={{ title: 'Profile' }} />
          <Stack.Screen name="GroupSettings" component={GroupSettingsScreen} options={({ route }) => ({ title: `${route.params.groupName} Settings` })} />
          <Stack.Screen name="Insights" component={InsightsScreen} options={({ route }) => ({ title: `${route.params.groupName} Insights` })} />
          <Stack.Screen name="TaskCalendar" component={TaskCalendarScreen} options={({ route }) => ({ title: `${route.params.groupName} Calendar` })} />
          <Stack.Screen name="Settings" component={SettingsScreen} options={{ title: 'Settings' }} />
          <Stack.Screen name="Membership" component={MembershipScreen} options={{ title: 'Membership' }} />
          <Stack.Screen name="HelpChat" component={HelpChatScreen} options={{ title: 'Splitmate Help' }} />
          <Stack.Screen name="Invites" component={InvitesScreen} options={{ title: 'Group invites' }} />
        </>
      )}
    </Stack.Navigator>
  );
}
