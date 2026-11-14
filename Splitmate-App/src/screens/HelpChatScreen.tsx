import { ComponentRef, useRef, useState } from 'react';
import { KeyboardAvoidingView, Platform, Pressable, ScrollView, StyleSheet, TextInput, View } from 'react-native';
import { Icon } from '@/components/Icon';

import { AppText as Text } from '@/components/AppText';
import { colors, fonts, radius, spacing } from '@/theme/colors';
import { typography } from '@/theme/typography';

type Message = { id: number; role: 'bot' | 'user'; text: string };

/**
 * Same keyword FAQ as the website's Splitmate Help chat, with directions that
 * point at the app's screens. It's a quick helper, not a live person or an AI.
 */
export function supportReply(message: string) {
  const text = message.toLowerCase();

  if (!text.trim()) {
    return 'Tell me what is happening and I will point you to the right place.';
  }
  if (/(invite|join|member|friend|email)/.test(text)) {
    return 'For invite issues, open the group and tap Manage, then Invite to Group. If email sending is not working, share the invite link it gives you. Invites you received show under Group Invites on the Profile screen.';
  }
  if (/(group|create|admin|nickname|remove)/.test(text)) {
    return 'For group issues, tap Groups on Home, or Create Group. Only the group admin can invite, set nicknames, or remove members, from the group\'s Manage screen.';
  }
  if (/(split|expense|owe|owed|payment|settle|amount|receipt)/.test(text)) {
    return 'For split issues, open the group, tap Expense, then set the amount, payer, and split method. Check the Pay tab for balances and payment history before recording another payment.';
  }
  if (/(task|reminder|calendar|due|notify|notification)/.test(text)) {
    return 'For task reminders, add a reminder time when you create the task, then make sure Task Notifications is on in Settings and that notifications are allowed for Splitmate on your phone.';
  }
  if (/(note|notes|grocery|price|list|compare)/.test(text)) {
    return 'Notes can be plain text. The compare prices button only appears for grocery, shopping, or list-style notes, so rent or normal reminders stay clean.';
  }
  if (/(theme|dark|light|color|logo)/.test(text)) {
    return 'Theme is in Settings. Pick System, Light, or Dark and an accent color, then restart Splitmate to apply it everywhere.';
  }
  if (/(point|points|reward|gift|redeem|cash|money)/.test(text)) {
    return 'Earning Splitmate Points is paused for now. Points you already have are kept, and rewards become available when your points reach the listed tier on your Profile.';
  }
  if (/(premium|membership|subscribe|subscription|plus|ads|ad)/.test(text)) {
    return 'Membership is on your Profile. Free keeps the core app, while Plus is planned for an ad-light experience, richer grocery price tools, and advanced insights after store billing is connected.';
  }
  if (/(launch|android|ios|store|app store|play store)/.test(text)) {
    return 'For launch, the biggest items are building the app package, adding app-store billing where needed, testing payments and rewards,the privacy policy, screenshots, and store review submission.';
  }
  if (/(profile|password|qr|account|login)/.test(text)) {
    return 'For account issues, open Profile from the top-left button. You can edit details, change your password, show your profile QR, and open Settings from there.';
  }
  if (/(https|http|phone|mobile|laptop|local|server|connect|network)/.test(text)) {
    return 'If the app can\'t reach Splitmate, check the Mobile API URL in Settings. For local testing it should be your computer\'s address on the same Wi-Fi, like http://192.168.1.20:5000/api/mobile.';
  }
  return 'I can help with groups, invites, splits, notes, tasks, notifications, theme, profile, and connection issues. Try describing which screen you are on and what you tapped.';
}

export function HelpChatScreen() {
  const [messages, setMessages] = useState<Message[]>([
    { id: 0, role: 'bot', text: 'Hi, I can help troubleshoot Splitmate. Tell me what is not working.' }
  ]);
  const [draft, setDraft] = useState('');
  const nextId = useRef(1);
  const scroller = useRef<ComponentRef<typeof ScrollView>>(null);

  function send() {
    const message = draft.trim();
    if (!message) {
      return;
    }
    const userId = nextId.current++;
    const botId = nextId.current++;
    setDraft('');
    setMessages(current => [...current, { id: userId, role: 'user', text: message }]);
    setTimeout(() => {
      setMessages(current => [...current, { id: botId, role: 'bot', text: supportReply(message) }]);
    }, 250);
  }

  return (
    <KeyboardAvoidingView style={styles.container} behavior={Platform.OS === 'ios' ? 'padding' : undefined} keyboardVerticalOffset={90}>
      <ScrollView
        ref={scroller}
        contentContainerStyle={styles.log}
        onContentSizeChange={() => scroller.current?.scrollToEnd({ animated: true })}
      >
        <Text style={styles.disclaimer}>Instant answers to common questions. This isn't a live person.</Text>
        {messages.map(message => (
          <View key={message.id} style={[styles.bubble, message.role === 'user' ? styles.userBubble : styles.botBubble]}>
            <Text style={[styles.bubbleText, message.role === 'user' && styles.userText]}>{message.text}</Text>
          </View>
        ))}
      </ScrollView>
      <View style={styles.composer}>
        <TextInput
          value={draft}
          onChangeText={setDraft}
          onSubmitEditing={send}
          placeholder="Ask about invites, splits, tasks..."
          placeholderTextColor={colors.placeholder}
          returnKeyType="send"
          style={styles.input}
        />
        <Pressable hitSlop={12} accessibilityRole="button" accessibilityLabel="Send" onPress={send} style={styles.send}>
          <Icon name="send" size={18} color={colors.onPrimary} />
        </Pressable>
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.bg
  },
  log: {
    padding: spacing.lg,
    gap: spacing.sm
  },
  disclaimer: {
    color: colors.muted,
    ...typography.caption,
    textAlign: 'center',
    marginBottom: spacing.xs
  },
  bubble: {
    maxWidth: '85%',
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    borderRadius: radius.lg
  },
  botBubble: {
    alignSelf: 'flex-start',
    backgroundColor: colors.surface,
    borderBottomLeftRadius: radius.sm
  },
  userBubble: {
    alignSelf: 'flex-end',
    backgroundColor: colors.primary,
    borderBottomRightRadius: radius.sm
  },
  bubbleText: {
    color: colors.text,
    ...typography.body
  },
  userText: {
    color: colors.onPrimary
  },
  composer: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    padding: spacing.md,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    backgroundColor: colors.surface
  },
  input: {
    flex: 1,
    minHeight: 44,
    paddingHorizontal: spacing.md,
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: colors.borderStrong,
    backgroundColor: colors.input,
    color: colors.ink,
    fontFamily: fonts.regular,
    fontSize: 16,
    lineHeight: 24
  },
  send: {
    width: 44,
    height: 44,
    borderRadius: radius.pill,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.primary
  }
});
