/**
 * Jest configuration for the mobile app.
 *
 * We avoid using the jest-expo preset directly because bun's node_modules
 * linker (.bun/ paths) causes module resolution failures in jest-expo's
 * setup files. Instead, we manually configure the essential parts:
 * - babel-jest transform with babel-preset-expo
 * - react-native test environment
 * - Proper transformIgnorePatterns for bun's .bun/ directory structure
 */

module.exports = {
  // Use react-native's custom test environment (node + react-native export conditions)
  testEnvironment: require.resolve("react-native/jest/react-native-env"),

  // Transform TypeScript/JSX via babel with the Expo preset
  transform: {
    "\\.[jt]sx?$": [
      "babel-jest",
      {
        caller: { name: "metro", bundler: "metro", platform: "ios" },
      },
    ],
  },

  // Allow transforming RN and Expo packages inside node_modules.
  // The (\\.bun/[^/]+/node_modules/)? prefix handles bun's linker structure.
  transformIgnorePatterns: [
    "node_modules/(?!(\\.bun/[^/]+/node_modules/)?((jest-)?react-native|@react-native(-community)?|expo(nent)?|@expo(nent)?/.*|@expo-google-fonts/.*|react-navigation|@react-navigation/.*|@sentry/react-native|native-base|react-native-svg|@quant/shared|victory-native|react-native-reanimated))",
  ],

  // Run RN's jest setup first (mocks core RN components),
  // then our custom setup (mocks Expo modules, async-storage, etc.)
  setupFiles: [require.resolve("react-native/jest/setup")],

  setupFilesAfterEnv: [
    "@testing-library/jest-native/extend-expect",
    "<rootDir>/src/test/setup.ts",
  ],

  moduleNameMapper: {
    // Resolve @/ path alias
    "^@/(.*)$": "<rootDir>/$1",
    // Map react-native-vector-icons to expo vector icons (same as jest-expo)
    "^react-native-vector-icons$": "@expo/vector-icons",
    "^react-native-vector-icons/(.*)": "@expo/vector-icons/$1",
  },

  // Use haste module system for react-native platform-specific files
  haste: {
    defaultPlatform: "ios",
    platforms: ["android", "ios", "native"],
  },

  // File extensions to consider
  moduleFileExtensions: ["ts", "tsx", "js", "jsx", "json", "node"],
};
