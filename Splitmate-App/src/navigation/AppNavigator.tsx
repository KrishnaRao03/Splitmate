import { createNativeStackNavigator } from '@react-navigation/native-stack';

import { colors } from '@/theme/colors';
import type { RootStackParamList } from '@/types';
import { useAuth } from '@/state/AuthContext';
import { LoadingState } from '@/components/States';
import { AddExpenseScreen } from '@/screens/AddExpenseScreen';
import { AddTaskScreen } from '@/screens/AddTaskScreen';
import { AuthScreen } from '@/screens/AuthScreen';
import { GroupDetailScreen } from '@/screens/GroupDetailScreen';
import { HomeScreen } from '@/screens/HomeScreen';
import { SettingsScreen } from '@/screens/SettingsScreen';

const Stack = createNativeStackNavigator<RootStackParamList>();

export function AppNavigator() {
  const { isLoading, token } = useAuth();

  if (isLoading) {
    return <LoadingState />;
  }

  return (
    <Stack.Navigator
      screenOptions={{
        headerStyle: { backgroundColor: colors.bg },
        headerShadowVisible: false,
        headerTintColor: colors.ink,
        headerTitleStyle: { fontWeight: '800' },
        contentStyle: { backgroundColor: colors.bg }
      }}
    >
      {!token ? (
        <Stack.Screen name="Auth" component={AuthScreen} options={{ headerShown: false }} />
      ) : (
        <>
          <Stack.Screen name="Home" component={HomeScreen} options={{ title: 'Splitmate' }} />
          <Stack.Screen name="GroupDetail" component={GroupDetailScreen} options={({ route }) => ({ title: route.params.groupName })} />
          <Stack.Screen name="AddExpense" component={AddExpenseScreen} options={{ title: 'Add Expense' }} />
          <Stack.Screen name="AddTask" component={AddTaskScreen} options={{ title: 'Add Task' }} />
          <Stack.Screen name="Settings" component={SettingsScreen} options={{ title: 'Settings' }} />
        </>
      )}
    </Stack.Navigator>
  );
}
