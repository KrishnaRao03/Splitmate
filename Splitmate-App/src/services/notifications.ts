import { Platform } from 'react-native';
import * as Device from 'expo-device';
import * as Notifications from 'expo-notifications';

import { api } from '@/api/client';
import type { Task } from '@/types';

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

  if (finalStatus !== 'granted' || !Device.isDevice) {
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

export async function scheduleTaskReminders(tasks: Task[]) {
  await Notifications.cancelAllScheduledNotificationsAsync();

  const now = Date.now();
  const scheduled: string[] = [];

  for (const task of tasks) {
    if (!task.reminder_time || task.is_completed) {
      continue;
    }

    const reminderDate = new Date(task.reminder_time);
    if (Number.isNaN(reminderDate.getTime()) || reminderDate.getTime() <= now) {
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
