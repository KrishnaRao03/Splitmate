import Constants, { ExecutionEnvironment } from 'expo-constants';
import { Platform } from 'react-native';
import * as Device from 'expo-device';
import * as Notifications from 'expo-notifications';

import { api } from '@/api/client';
import { TASK_NOTIFICATIONS_KEY, storedTaskNotificationsEnabled, writePreference } from '@/theme/preferences';
import type { Task } from '@/types';
import { parseServerDate } from '@/utils/dates';

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldPlaySound: true,
    shouldSetBadge: true,
    shouldShowBanner: true,
    shouldShowList: true
  })
});

export async function configureNotifications() {
  if (Platform.OS === 'android') {
    await Notifications.setNotificationChannelAsync('task-reminders', {
      name: 'Task reminders',
      importance: Notifications.AndroidImportance.HIGH,
      vibrationPattern: [0, 250, 250, 250],
      lightColor: '#0e7aa6'
    });
  }

  const permissions = await Notifications.getPermissionsAsync();
  let finalStatus = permissions.status;
  if (finalStatus !== 'granted') {
    const requested = await Notifications.requestPermissionsAsync();
    finalStatus = requested.status;
  }

  // Expo Go dropped remote push in SDK 53, so asking for a push token there only
  // logs errors. Local task reminders still work; push needs a development build.
  const inExpoGo = Constants.executionEnvironment === ExecutionEnvironment.StoreClient;
  if (finalStatus !== 'granted' || !Device.isDevice || inExpoGo) {
    return { granted: finalStatus === 'granted', token: null };
  }

  try {
    const token = (await Notifications.getExpoPushTokenAsync()).data;
    await api.registerDevice(token, Platform.OS);
    return { granted: true, token };
  } catch (error) {
    return { granted: true, token: null };
  }
}

export type NotificationPermission = 'allowed' | 'blocked' | 'not asked' | 'not supported';

/** Mirrors the website's "Browser Permission" status line. */
export async function notificationPermissionStatus(): Promise<NotificationPermission> {
  if (Platform.OS === 'web') {
    return 'not supported';
  }
  try {
    const { status } = await Notifications.getPermissionsAsync();
    if (status === 'granted') {
      return 'allowed';
    }
    return status === 'denied' ? 'blocked' : 'not asked';
  } catch {
    return 'not supported';
  }
}

export function taskNotificationsEnabled() {
  return storedTaskNotificationsEnabled();
}

/** Turning reminders off cancels everything already scheduled on this device. */
export async function setTaskNotificationsEnabled(enabled: boolean) {
  await writePreference(TASK_NOTIFICATIONS_KEY, enabled ? 'on' : 'off');
  if (!enabled && Platform.OS !== 'web') {
    await Notifications.cancelAllScheduledNotificationsAsync().catch(() => undefined);
  }
}

export async function scheduleTaskReminders(tasks: Task[]) {
  if (Platform.OS === 'web') {
    return [];
  }
  await Notifications.cancelAllScheduledNotificationsAsync();
  if (!storedTaskNotificationsEnabled()) {
    return [];
  }

  const now = Date.now();
  const scheduled: string[] = [];

  for (const task of tasks) {
    if (!task.reminder_time || task.is_completed) {
      continue;
    }

    const reminderDate = parseServerDate(task.reminder_time);
    if (!reminderDate || reminderDate.getTime() <= now) {
      continue;
    }

    const notificationId = await Notifications.scheduleNotificationAsync({
      content: {
        title: task.title,
        body: `${task.group_name} reminder${task.description ? `: ${task.description}` : ''}`,
        sound: true,
        data: { taskId: task.id, groupId: task.group_id }
      },
      trigger: {
        type: Notifications.SchedulableTriggerInputTypes.DATE,
        date: reminderDate,
        channelId: 'task-reminders'
      }
    });
    scheduled.push(notificationId);
  }

  return scheduled;
}
