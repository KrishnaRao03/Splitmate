/** The shopper's location for grocery price lookups (city, postal code or "lat, lng"). Remembered on this device. */
const STORAGE_KEY = 'splitmate.groceryLocation';
let current = '';

function storage(): Storage | null {
  try {
    return typeof localStorage === 'undefined' ? null : localStorage;
  } catch {
    return null;
  }
}

export function getGroceryLocation() {
  if (!current) {
    try {
      current = storage()?.getItem(STORAGE_KEY) ?? '';
    } catch {
      current = '';
    }
  }
  return current;
}

export function setGroceryLocation(value: string) {
  current = value.trim();
  try {
    storage()?.setItem(STORAGE_KEY, current);
  } catch {
    // Remembering it is only a convenience.
  }
}

/** Asks the browser/device for the current position. Resolves to "lat, lng" or rejects with a readable message. */
export function currentPositionText(): Promise<string> {
  const geo = typeof navigator !== 'undefined' ? navigator.geolocation : undefined;
  if (!geo) {
    return Promise.reject(new Error('Location is not available here. Type your city or postal code instead.'));
  }
  return new Promise((resolve, reject) => {
    geo.getCurrentPosition(
      position => resolve(`${position.coords.latitude.toFixed(3)}, ${position.coords.longitude.toFixed(3)}`),
      () => reject(new Error('Location permission was denied. Type your city or postal code instead.')),
      { enableHighAccuracy: false, timeout: 15000, maximumAge: 10 * 60 * 1000 }
    );
  });
}
