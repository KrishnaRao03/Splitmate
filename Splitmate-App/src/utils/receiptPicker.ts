import * as ImagePicker from 'expo-image-picker';
import { Platform } from 'react-native';

import { notify } from '@/state/UndoToast';

export type ReceiptFile = { uri: string; name: string; mimeType?: string; file?: File };

/**
 * Opens the camera or photo library for a receipt. Resolves to the image, or null if cancelled.
 * On the web build the file picker opens at once (no permission step), because browsers only
 * allow it straight after a tap.
 */
export async function pickReceiptImage(source: 'camera' | 'library'): Promise<ReceiptFile | null> {
  if (Platform.OS !== 'web') {
    const permission = source === 'camera'
      ? await ImagePicker.requestCameraPermissionsAsync()
      : await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!permission.granted) {
      notify(
        source === 'camera' ? 'Camera access needed' : 'Photo access needed',
        `Allow Splitmate to use your ${source === 'camera' ? 'camera' : 'photos'} in your phone's settings to scan receipts.`
      );
      return null;
    }
  }
  // A slightly compressed photo keeps uploads well under the server's 5 MB limit.
  const options: ImagePicker.ImagePickerOptions = { mediaTypes: ['images'], quality: 0.7 };
  const result = source === 'camera' && Platform.OS !== 'web'
    ? await ImagePicker.launchCameraAsync(options)
    : await ImagePicker.launchImageLibraryAsync(options);
  if (result.canceled) {
    return null;
  }
  const asset = result.assets[0];
  return {
    uri: asset.uri,
    name: asset.fileName || 'receipt.jpg',
    mimeType: asset.mimeType || 'image/jpeg',
    file: asset.file
  };
}
