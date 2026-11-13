import { useFocusEffect, useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useCallback, useMemo, useRef, useState } from 'react';
import { Alert, Pressable, StyleSheet, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { api } from '@/api/client';
import { AppButton } from '@/components/AppButton';
import { AppText as Text } from '@/components/AppText';
import { Card } from '@/components/Card';
import { ChoiceChips } from '@/components/ChoiceChips';
import { GroceryComparisonView } from '@/components/GroceryComparisonView';
import { Screen } from '@/components/Screen';
import { EmptyState, ErrorState, LoadingState } from '@/components/States';
import { TextField } from '@/components/TextField';
import { colors, radius, spacing } from '@/theme/colors';
import { typography } from '@/theme/typography';
import type { GroceryComparison, Group, Note, RootStackParamList } from '@/types';

export function NotesScreen() {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  const [comparisons, setComparisons] = useState<Record<number, GroceryComparison>>({});
  const [priceItems, setPriceItems] = useState('');
  const [priceResult, setPriceResult] = useState<GroceryComparison | null>(null);
  const [priceLoading, setPriceLoading] = useState(false);
  const [priceError, setPriceError] = useState('');
  const [notes, setNotes] = useState<Note[]>([]);
  const [groups, setGroups] = useState<Group[]>([]);
  const [adding, setAdding] = useState(false);
  const [newGroupId, setNewGroupId] = useState<number | null>(null);
  const [newTitle, setNewTitle] = useState('');
  const [newDescription, setNewDescription] = useState('');
  const [savingNew, setSavingNew] = useState(false);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const hasLoaded = useRef(false);
  const [search, setSearch] = useState('');
  const [groupFilter, setGroupFilter] = useState<number | 'all'>('all');
  const [editingNoteId, setEditingNoteId] = useState<number | null>(null);
  const [editTitle, setEditTitle] = useState('');
  const [editDescription, setEditDescription] = useState('');

  const load = useCallback(async () => {
    try {
      const [data, groupData] = await Promise.all([api.allNotes(), api.groups()]);
      setNotes(data);
      setGroups(groupData);
      hasLoaded.current = true;
      setLoadError(null);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Try again.';
      setLoadError(message);
      if (hasLoaded.current) {
        Alert.alert('Could not refresh Notes', message);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  const refresh = useCallback(async () => {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  }, [load]);

  useFocusEffect(useCallback(() => {
    load();
  }, [load]));

  async function runAction(action: () => Promise<unknown>, title: string) {
    try {
      await action();
      await load();
    } catch (error) {
      Alert.alert(title, error instanceof Error ? error.message : 'Try again.');
    }
  }

  async function addNote() {
    const groupId = newGroupId ?? (groups.length === 1 ? groups[0].id : null);
    const title = newTitle.trim();
    if (!groupId) {
      Alert.alert('Choose a group', 'Pick which group this note belongs to.');
      return;
    }
    if (!title) {
      Alert.alert('Title required', 'Enter a title for this note.');
      return;
    }
    setSavingNew(true);
    await runAction(async () => {
      await api.addNote(groupId, { title, description: newDescription.trim() });
      setNewTitle('');
      setNewDescription('');
      setAdding(false);
    }, 'Could not add note');
    setSavingNew(false);
  }

  function beginEditNote(note: Note) {
    setEditingNoteId(note.id);
    setEditTitle(note.title);
    setEditDescription(note.description);
  }

  async function saveNote(noteId: number) {
    const title = editTitle.trim();
    if (!title) {
      Alert.alert('Title required', 'Enter a title for this note.');
      return;
    }
    await runAction(async () => {
      await api.updateNote(noteId, title, editDescription.trim());
      setEditingNoteId(null);
    }, 'Could not update note');
  }

  // Same grocery price comparison as the website, for shopping-list notes.
  async function compareNote(noteId: number) {
    if (comparisons[noteId]) {
      setComparisons(({ [noteId]: _hidden, ...rest }) => rest);
      return;
    }
    try {
      const comparison = await api.compareGroceries(noteId);
      setComparisons(current => ({ ...current, [noteId]: comparison }));
    } catch (error) {
      Alert.alert('Could not compare groceries', error instanceof Error ? error.message : 'Try again.');
    }
  }

  // Type a list, get real prices from Toronto grocery stores, cheapest store first.
  async function comparePrices() {
    if (!priceItems.trim()) {
      setPriceError('Type a few items, like: apple, banana, milk');
      return;
    }
    setPriceError('');
    setPriceLoading(true);
    try {
      setPriceResult(await api.compareGroceryList(priceItems));
    } catch (error) {
      setPriceResult(null);
      setPriceError(error instanceof Error ? error.message : 'Could not compare prices. Try again.');
    } finally {
      setPriceLoading(false);
    }
  }

  function confirmDeleteNote(note: Note) {
    Alert.alert('Delete note?', note.title, [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Delete', style: 'destructive', onPress: () => runAction(() => api.deleteNote(note.id), 'Could not delete note') }
    ]);
  }

  const groupOptions = useMemo(() => {
    const seen = new Map<number, string>();
    notes.forEach(note => {
      if (!seen.has(note.group_id)) {
        seen.set(note.group_id, note.group_name);
      }
    });
    return [{ label: 'All groups', value: 'all' as const }, ...Array.from(seen.entries()).map(([id, name]) => ({ label: name, value: id }))];
  }, [notes]);

  const filteredNotes = useMemo(() => {
    const query = search.trim().toLowerCase();
    return notes.filter(note => {
      if (groupFilter !== 'all' && note.group_id !== groupFilter) {
        return false;
      }
      if (!query) {
        return true;
      }
      return note.title.toLowerCase().includes(query) || note.description.toLowerCase().includes(query);
    });
  }, [notes, groupFilter, search]);

  if (loading && !hasLoaded.current) {
    return <LoadingState label="Loading your notes..." />;
  }
  if (loadError && !hasLoaded.current) {
    return <ErrorState message={loadError} onRetry={() => { setLoading(true); load(); }} />;
  }

  return (
    <View style={styles.page}>
    <Screen onRefresh={refresh} refreshing={refreshing}>
      <View style={styles.rowBetween}>
        <Text style={styles.sectionTitle}>Notes</Text>
        {groups.length && !adding ? (
          <AppButton icon="add-outline" onPress={() => setAdding(true)}>Add Note</AppButton>
        ) : null}
      </View>

      <Card style={styles.filterCard}>
        <Text style={styles.title}>Compare grocery prices</Text>
        <Text style={styles.muted}>Type what you need and see which store is cheapest right now.</Text>
        <TextField
          label="Items"
          value={priceItems}
          onChangeText={setPriceItems}
          placeholder="apple, banana, 2 milk, bread"
          multiline
          error={priceError}
        />
        <AppButton icon="pricetags-outline" loading={priceLoading} onPress={comparePrices}>
          {priceLoading ? 'Checking store prices...' : 'Compare prices'}
        </AppButton>
        {priceResult ? <GroceryComparisonView comparison={priceResult} /> : null}
      </Card>

      {!groups.length ? (
        <Card style={styles.filterCard}>
          <EmptyState label="Notes belong to a group. Join or create a group to start adding notes." />
          <AppButton icon="people-outline" onPress={() => navigation.navigate('CreateGroup')}>Create a Group</AppButton>
        </Card>
      ) : adding ? (
        <Card style={styles.filterCard}>
          <Text style={styles.title}>New note</Text>
          {groups.length > 1 ? (
            <ChoiceChips<number>
              label="Group"
              value={newGroupId}
              onChange={setNewGroupId}
              options={groups.map(group => ({ label: group.name, value: group.id }))}
            />
          ) : (
            <Text style={styles.muted}>For {groups[0].name}</Text>
          )}
          <TextField label="Title" value={newTitle} onChangeText={setNewTitle} placeholder="Grocery list, Wi-Fi password" />
          <TextField label="Description (optional)" value={newDescription} onChangeText={setNewDescription} multiline placeholder="milk, bread, eggs" />
          <Text style={styles.muted}>Tip: call it a grocery or shopping list and put one item per line (or separate with commas) to compare store prices.</Text>
          <View style={styles.actionRow}>
            <AppButton icon="save-outline" style={styles.actionButton} loading={savingNew} onPress={addNote}>Save</AppButton>
            <AppButton icon="close-outline" variant="outline" style={styles.actionButton} onPress={() => setAdding(false)}>Cancel</AppButton>
          </View>
        </Card>
      ) : null}

      {notes.length ? (
        <Card style={styles.filterCard}>
          <TextField
            label="Search"
            placeholder="Search notes"
            value={search}
            onChangeText={setSearch}
          />
          {groupOptions.length > 2 ? (
            <ChoiceChips
              label="Group"
              options={groupOptions}
              value={groupFilter}
              onChange={setGroupFilter}
            />
          ) : null}
        </Card>
      ) : null}

      {notes.length === 0 ? (
        groups.length && !adding ? (
          <Card style={styles.filterCard}>
            <EmptyState label="No notes yet. Keep shared lists, codes and reminders here." />
            <AppButton icon="add-outline" onPress={() => setAdding(true)}>Add Your First Note</AppButton>
          </Card>
        ) : null
      ) : filteredNotes.length === 0 ? (
        <EmptyState label="No notes match your search." />
      ) : filteredNotes.map(note => (
        <Card key={note.id} style={styles.noteCard}>
          {editingNoteId === note.id ? (
            <>
              <TextField label="Title" value={editTitle} onChangeText={setEditTitle} />
              <TextField label="Description" value={editDescription} onChangeText={setEditDescription} multiline />
              <View style={styles.actionRow}>
                <AppButton icon="save-outline" style={styles.actionButton} onPress={() => saveNote(note.id)}>Save</AppButton>
                <AppButton icon="close-outline" variant="outline" style={styles.actionButton} onPress={() => setEditingNoteId(null)}>Cancel</AppButton>
              </View>
            </>
          ) : (
            <>
              <Pressable onPress={() => runAction(() => api.toggleNote(note.id), 'Could not update note')} style={styles.rowBetween}>
                <Text style={[styles.title, note.is_completed && styles.completed]}>{note.title}</Text>
                <Ionicons name={note.is_completed ? 'checkmark-circle' : 'ellipse-outline'} size={22} color={colors.primary} />
              </Pressable>
              {note.description ? <Text style={styles.description}>{note.description}</Text> : null}
              <Text style={styles.muted}>{note.group_name} - by {note.created_by}</Text>
              <View style={styles.iconActionRow}>
                {note.can_compare_prices ? (
                  <Pressable accessibilityLabel={`Compare ${note.title} grocery prices`} onPress={() => compareNote(note.id)} style={styles.iconButton}>
                    <Ionicons name={comparisons[note.id] ? 'close-outline' : 'cart-outline'} size={20} color={colors.primaryDark} />
                  </Pressable>
                ) : null}
                <Pressable accessibilityLabel={`Edit ${note.title}`} onPress={() => beginEditNote(note)} style={styles.iconButton}>
                  <Ionicons name="pencil-outline" size={20} color={colors.primaryDark} />
                </Pressable>
                {note.can_delete ? (
                  <Pressable accessibilityLabel={`Delete ${note.title}`} onPress={() => confirmDeleteNote(note)} style={styles.iconButton}>
                    <Ionicons name="trash-outline" size={20} color={colors.danger} />
                  </Pressable>
                ) : null}
              </View>
              {comparisons[note.id] ? <GroceryComparisonView comparison={comparisons[note.id]} /> : null}
            </>
          )}
        </Card>
      ))}
    </Screen>
      {groups.length ? (
        <Pressable style={styles.fab} onPress={() => setAdding(true)} accessibilityRole="button" accessibilityLabel="Add note">
          <Ionicons name="add" size={30} color={colors.surface} />
        </Pressable>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  page: {
    flex: 1
  },
  fab: {
    position: 'absolute',
    right: spacing.lg,
    bottom: spacing.lg,
    width: 58,
    height: 58,
    borderRadius: 29,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.primary,
    elevation: 6,
    shadowColor: colors.ink,
    shadowOpacity: 0.2,
    shadowRadius: 8,
    shadowOffset: { width: 0, height: 4 }
  },
  sectionTitle: {
    color: colors.ink,
    ...typography.h2
  },
  filterCard: {
    gap: spacing.md
  },
  noteCard: {
    gap: spacing.sm
  },
  title: {
    color: colors.ink,
    ...typography.h3
  },
  completed: {
    color: colors.muted,
    textDecorationLine: 'line-through'
  },
  description: {
    color: colors.text,
    ...typography.body
  },
  muted: {
    color: colors.muted,
    ...typography.caption
  },
  rowBetween: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: spacing.sm
  },
  actionRow: {
    flexDirection: 'row',
    gap: spacing.sm
  },
  actionButton: {
    flex: 1
  },
  iconActionRow: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    gap: spacing.sm
  },
  iconButton: {
    width: 40,
    height: 40,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: radius.sm,
    backgroundColor: colors.surfaceAlt
  }
});
