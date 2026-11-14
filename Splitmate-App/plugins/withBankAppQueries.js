const { withAndroidManifest } = require('@expo/config-plugins');

const banks = require('../src/utils/canadian-banks.json');

// Android 11+ hides other apps unless the manifest lists them in <queries>, so the
// "Open my bank" button could not launch the banking app without this.
module.exports = function withBankAppQueries(config) {
  return withAndroidManifest(config, (config) => {
    const manifest = config.modResults.manifest;
    const queries = manifest.queries?.[0] ?? {};
    const packages = queries.package ?? [];
    const listed = new Set(packages.map((entry) => entry.$['android:name']));

    for (const bank of banks) {
      if (!listed.has(bank.androidPackage)) {
        packages.push({ $: { 'android:name': bank.androidPackage } });
      }
    }

    queries.package = packages;
    manifest.queries = [queries];
    return config;
  });
};
