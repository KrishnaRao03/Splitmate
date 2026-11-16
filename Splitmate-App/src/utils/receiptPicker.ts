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
  if (Platform.OS === 'web' && asset.file) {
    // The browser picker ignores `quality`, so full-size phone photos (often 3 to 8 MB, or HEIC)
    // are shrunk to a JPEG here; big uploads were timing out and the scanner rejects HEIC.
    const small = await shrinkForUpload(asset.file).catch(() => null);
    if (small) {
      return { uri: URL.createObjectURL(small), name: 'receipt.jpg', mimeType: 'image/jpeg', file: small };
    }
  }
  return {
    uri: asset.uri,
    name: asset.fileName || 'receipt.jpg',
    mimeType: asset.mimeType || 'image/jpeg',
    file: asset.file
  };
}

const MAX_SIDE = 1600;

/** Redraws a picked photo at most 1600 px on its long side as a JPEG, which is plenty to read a receipt. */
async function shrinkForUpload(file: File): Promise<File> {
  const url = URL.createObjectURL(file);
  try {
    const image = await new Promise<HTMLImageElement>((resolve, reject) => {
      const element = new Image();
      element.onload = () => resolve(element);
      element.onerror = () => reject(new Error('Could not read that photo.'));
      element.src = url;
    });
    const scale = Math.min(1, MAX_SIDE / Math.max(image.naturalWidth, image.naturalHeight));
    const canvas = document.createElement('canvas');
    canvas.width = Math.round(image.naturalWidth * scale);
    canvas.height = Math.round(image.naturalHeight * scale);
    canvas.getContext('2d')?.drawImage(image, 0, 0, canvas.width, canvas.height);
    const blob = await new Promise<Blob | null>(resolve => canvas.toBlob(resolve, 'image/jpeg', 0.82));
    if (!blob) {
      throw new Error('Could not shrink that photo.');
    }
    return new File([blob], 'receipt.jpg', { type: 'image/jpeg' });
  } finally {
    URL.revokeObjectURL(url);
  }
}
