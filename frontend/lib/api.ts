import type {
  InvestigationCreateResponse,
  InvestigationStateResponse,
  ServiceHealth,
} from './types';

/**
 * Single base URL for every backend call. Configured with
 * `NEXT_PUBLIC_API_URL` (see `frontend/.env.local.example`); the fallback only
 * applies when the variable is absent so a misconfigured deployment fails
 * visibly rather than silently pointing somewhere else.
 */
export const API_BASE_URL: string = (process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000').replace(
  /\/+$/,
  '',
);

/** FastAPI validation caps the claim at 4000 characters. */
export const MAX_CLAIM_LENGTH = 4000;

/**
 * The pipeline is synchronous and issues on the order of fifteen LLM round
 * trips, so a comfortable success window is minutes, not seconds. The timeout
 * is deliberately generous; it only exists to turn a wedged socket into a
 * readable error.
 */
const REQUEST_TIMEOUT_MS = 15 * 60 * 1000;

/** Raised for any non-2xx response or transport failure. */
export class ApiError extends Error {
  readonly status: number | null;
  readonly detail: string | null;

  constructor(message: string, status: number | null = null, detail: string | null = null) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

/** True when the failure means the investigation never produced a result. */
export function isNetworkFailure(error: unknown): boolean {
  return error instanceof ApiError && error.status === null;
}

interface RequestOptions {
  signal?: AbortSignal;
  method?: 'GET' | 'POST';
  body?: unknown;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { signal, method = 'GET', body } = options;

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  const abortOuter = () => controller.abort();
  signal?.addEventListener('abort', abortOuter);

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method,
      signal: controller.signal,
      headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch (cause) {
    // An outer abort means the user navigated away or cancelled deliberately.
    if (signal?.aborted) {
      throw new ApiError('Investigation cancelled.', null, 'cancelled');
    }
    if (cause instanceof Error && cause.name === 'AbortError') {
      throw new ApiError(
        'The backend did not respond in time. The investigation may still be running.',
        null,
        'timeout',
      );
    }
    throw new ApiError(
      `Could not reach the backend at ${API_BASE_URL}. Check that the API is running.`,
      null,
      'network',
    );
  } finally {
    clearTimeout(timeout);
    signal?.removeEventListener('abort', abortOuter);
  }

  const raw = await response.text();
  let payload: unknown = null;
  if (raw) {
    try {
      payload = JSON.parse(raw);
    } catch {
      payload = null;
    }
  }

  if (!response.ok) {
    // FastAPI reports errors as `{ detail: string }`; validation errors use a
    // list of objects instead, so both shapes are handled.
    const detail = extractDetail(payload) ?? `Request failed with status ${response.status}.`;
    throw new ApiError(detail, response.status, detail);
  }

  if (payload === null) {
    throw new ApiError('The backend returned a response that could not be read.', response.status, null);
  }

  return payload as T;
}

function extractDetail(payload: unknown): string | null {
  if (payload === null || typeof payload !== 'object') {
    return null;
  }
  const detail = (payload as { detail?: unknown }).detail;
  if (typeof detail === 'string') {
    return detail;
  }
  if (Array.isArray(detail)) {
    const messages = detail
      .map((entry) => {
        if (entry && typeof entry === 'object' && 'msg' in entry) {
          return String((entry as { msg: unknown }).msg);
        }
        return null;
      })
      .filter((entry): entry is string => Boolean(entry));
    return messages.length > 0 ? messages.join(' ') : null;
  }
  return null;
}

/** Runs a new investigation. Resolves only once the pipeline has finished. */
export function createInvestigation(claim: string, signal?: AbortSignal): Promise<InvestigationCreateResponse> {
  return request<InvestigationCreateResponse>('/api/v1/investigations', {
    method: 'POST',
    body: { claim },
    signal,
  });
}

/** Loads the full persisted result of an investigation. */
export function getInvestigation(claimId: number, signal?: AbortSignal): Promise<InvestigationStateResponse> {
  return request<InvestigationStateResponse>(`/api/v1/investigations/${claimId}`, { signal });
}

/**
 * Non-probing service health, used for the connection indicator. This reads
 * configuration only and never consumes provider quota.
 */
export function getHealth(signal?: AbortSignal): Promise<ServiceHealth> {
  return request<ServiceHealth>('/health', { signal });
}
