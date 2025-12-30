import * as Sentry from '@sentry/svelte';

let sentryInitialized = false;

// Initialize Sentry from backend config
async function initSentry() {
	if (sentryInitialized) return;

	try {
		const response = await fetch('/api/config');
		const config = await response.json();

		if (config.sentry?.dsn) {
			Sentry.init({
				dsn: config.sentry.dsn,
				environment: config.sentry.environment || 'production',
				integrations: [Sentry.browserTracingIntegration()],
				tracesSampleRate: 1.0
			});
			sentryInitialized = true;
		}
	} catch (e) {
		console.error('Failed to initialize Sentry:', e);
	}
}

// Initialize immediately
initSentry();

export const handleError = ({ error }: { error: unknown; event: unknown }) => {
	if (sentryInitialized) {
		Sentry.captureException(error);
	}
	console.error('Client error:', error);
};
