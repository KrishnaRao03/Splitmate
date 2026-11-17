const { withAndroidManifest } = require('@expo/config-plugins');

// Plain HTTP is only for talking to the dev server on your own network. Production builds
// (eas.json sets SPLITMATE_ALLOW_CLEARTEXT=false) leave it off, so passwords and tokens always go over HTTPS.
module.exports = function withCleartextTraffic(config) {
  if (process.env.SPLITMATE_ALLOW_CLEARTEXT === 'false') {
    return config;
  }

  return withAndroidManifest(config, (config) => {
    const application = config.modResults.manifest.application?.[0];

    if (application) {
      application.$['android:usesCleartextTraffic'] = 'true';
    }

    return config;
  });
};
