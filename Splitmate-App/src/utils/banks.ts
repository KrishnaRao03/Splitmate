import AsyncStorage from '@react-native-async-storage/async-storage';
import * as Clipboard from 'expo-clipboard';
import * as IntentLauncher from 'expo-intent-launcher';
import { Linking, Platform } from 'react-native';

import banks from './canadian-banks.json';

export type Bank = { id: string; name: string; androidPackage: string; website: string };

export const CANADIAN_BANKS: Bank[] = banks;
const BANK_KEY = 'splitmate.preferred.bank';

export async function getPreferredBankId() {
  try {
    return await AsyncStorage.getItem(BANK_KEY);
  } catch {
    return null;
  }
}

export async function setPreferredBankId(bankId: string) {
  try {
    await AsyncStorage.setItem(BANK_KEY, bankId);
  } catch {
    // Only a convenience; the user can pick the bank again.
  }
}

export async function copyText(text: string) {
  await Clipboard.setStringAsync(text);
}

/**
 * Opens the user's banking app so they can send (or request) the e-Transfer themselves.
 * Android launches the installed app; iOS and phones without the app get the bank's website.
 */
export async function openBank(bank: Bank) {
  if (Platform.OS === 'android') {
    try {
      IntentLauncher.openApplication(bank.androidPackage);
      return;
    } catch {
      // Not installed, or hidden by Android package visibility (e.g. in Expo Go): fall back to the website.
    }
  }
  await Linking.openURL(bank.website);
}
