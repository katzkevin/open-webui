import * as Sentry from '@sentry/svelte';

const SENTRY_DSN = import.meta.env.VITE_SENTRY_DSN;
const SENTRY_ENVIRONMENT = import.meta.env.VITE_SENTRY_ENVIRONMENT || 'production';

if (SENTRY_DSN) {
	Sentry.init({
		dsn: SENTRY_DSN,
		environment: SENTRY_ENVIRONMENT,
		integrations: [Sentry.browserTracingIntegration()],
		tracesSampleRate: 1.0
	});
}

export const handleError = ({ error, event }: { error: unknown; event: unknown }) => {
	if (SENTRY_DSN) {
		Sentry.captureException(error);
	}
	console.error('Client error:', error);
};
