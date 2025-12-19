import { describe, it, expect, vi, beforeEach } from 'vitest';
import axios, { AxiosError } from 'axios';
import { getErrorMessage } from './client';

// Mock axios
vi.mock('axios', async () => {
  const actual = await vi.importActual('axios');
  return {
    ...actual,
    default: {
      create: vi.fn(() => ({
        get: vi.fn(),
        post: vi.fn(),
        interceptors: {
          request: { use: vi.fn() },
          response: { use: vi.fn() },
        },
      })),
      isAxiosError: (actual as typeof axios).isAxiosError,
    },
  };
});

describe('getErrorMessage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('returns message for 400 Bad Request', () => {
    const error = createAxiosError(400);
    expect(getErrorMessage(error)).toBe('Invalid request. Please check your input.');
  });

  it('returns backend message for 400 if provided', () => {
    const error = createAxiosError(400, { message: 'Custom validation error' });
    expect(getErrorMessage(error)).toBe('Custom validation error');
  });

  it('returns message for 401 Unauthorized', () => {
    const error = createAxiosError(401);
    expect(getErrorMessage(error)).toBe('Authentication required. Please log in.');
  });

  it('returns message for 403 Forbidden', () => {
    const error = createAxiosError(403);
    expect(getErrorMessage(error)).toBe('You do not have permission to perform this action.');
  });

  it('returns message for 404 Not Found', () => {
    const error = createAxiosError(404);
    expect(getErrorMessage(error)).toBe('The requested resource was not found.');
  });

  it('returns message for 422 Unprocessable Entity', () => {
    const error = createAxiosError(422);
    expect(getErrorMessage(error)).toBe('Invalid data format. Please check your input.');
  });

  it('returns backend detail for 422 if provided', () => {
    const error = createAxiosError(422, { detail: 'Field validation failed' });
    expect(getErrorMessage(error)).toBe('Field validation failed');
  });

  it('returns message for 500 Internal Server Error', () => {
    const error = createAxiosError(500);
    expect(getErrorMessage(error)).toBe('An error occurred on the server. Please try again later.');
  });

  it('returns message for 503 Service Unavailable', () => {
    const error = createAxiosError(503);
    expect(getErrorMessage(error)).toBe('Service temporarily unavailable. Please try again later.');
  });

  it('returns network error message when no response', () => {
    const error = createAxiosError(null);
    expect(getErrorMessage(error)).toBe('Unable to connect to the server. Please check your connection.');
  });

  it('returns generic message for unknown status codes', () => {
    const error = createAxiosError(418); // I'm a teapot
    expect(getErrorMessage(error)).toBe('An unexpected error occurred. Please try again.');
  });

  it('handles standard Error objects', () => {
    const error = new Error('Standard error message');
    expect(getErrorMessage(error)).toBe('Standard error message');
  });

  it('handles unknown error types', () => {
    expect(getErrorMessage('string error')).toBe('An unexpected error occurred.');
    expect(getErrorMessage(null)).toBe('An unexpected error occurred.');
    expect(getErrorMessage(undefined)).toBe('An unexpected error occurred.');
    expect(getErrorMessage(123)).toBe('An unexpected error occurred.');
  });
});

// Helper function to create mock Axios errors
function createAxiosError(
  status: number | null,
  data?: { message?: string; detail?: string }
): AxiosError {
  const error = new Error('Request failed') as AxiosError;
  error.isAxiosError = true;
  error.name = 'AxiosError';
  error.config = { headers: {} as AxiosError['config']['headers'] };
  error.toJSON = () => ({});

  if (status !== null) {
    error.response = {
      status,
      statusText: 'Error',
      headers: {},
      config: { headers: {} as AxiosError['config']['headers'] },
      data: data || {},
    };
  } else {
    error.response = undefined;
  }

  return error;
}
