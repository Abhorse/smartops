/// Runtime configuration from `--dart-define` flags.
class AppConfig {
  const AppConfig({
    required this.apiBaseUrl,
    required this.appEnv,
    required this.googleClientId,
  });

  final String apiBaseUrl;
  final String appEnv;
  final String googleClientId;

  static const AppConfig instance = AppConfig(
    apiBaseUrl: String.fromEnvironment(
      'API_BASE_URL',
      defaultValue: 'http://10.0.2.2:8000',
    ),
    appEnv: String.fromEnvironment('APP_ENV', defaultValue: 'dev'),
    googleClientId: String.fromEnvironment('GOOGLE_CLIENT_ID', defaultValue: ''),
  );
}
