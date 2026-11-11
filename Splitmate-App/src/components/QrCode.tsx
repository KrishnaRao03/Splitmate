import { StyleSheet, View } from 'react-native';

/**
 * Draws a QR code from the server's module rows ("0101..."), merging each run of
 * dark modules into one View so a full code stays at a few hundred views.
 */
export function QrCode({ rows, size = 200 }: { rows: string[]; size?: number }) {
  const count = rows.length || 1;
  const quiet = 2; // quiet-zone modules around the code so scanners can find it
  const cell = size / (count + quiet * 2);

  return (
    <View style={[styles.frame, { width: size, height: size }]} accessibilityRole="image" accessibilityLabel="Profile QR code">
      {rows.map((row, y) => {
        const runs: Array<{ start: number; length: number }> = [];
        let start = -1;
        for (let x = 0; x <= row.length; x += 1) {
          const dark = row[x] === '1';
          if (dark && start < 0) {
            start = x;
          } else if (!dark && start >= 0) {
            runs.push({ start, length: x - start });
            start = -1;
          }
        }
        return runs.map(run => (
          <View
            key={`${y}-${run.start}`}
            style={[
              styles.module,
              {
                top: (y + quiet) * cell,
                left: (run.start + quiet) * cell,
                width: run.length * cell + 0.5,
                height: cell + 0.5
              }
            ]}
          />
        ));
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  frame: {
    position: 'relative',
    // QR codes must be dark-on-light to scan, so this stays white in dark mode too.
    backgroundColor: '#ffffff',
    borderRadius: 8,
    overflow: 'hidden',
    alignSelf: 'center'
  },
  module: {
    position: 'absolute',
    backgroundColor: '#000000'
  }
});
