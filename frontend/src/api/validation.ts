import { z } from 'zod';

/**
 * Zod schemas for runtime validation of claim data
 */

export const ClaimItemSchema = z.object({
  procedure_code: z.string().min(1, 'Procedure code is required'),
  diagnosis_code: z.string().optional(),
  quantity: z.number().int().positive('Quantity must be a positive integer'),
  line_amount: z.number().nonnegative('Line amount cannot be negative'),
  modifier: z.string().optional(),
});

export const ClaimSubmissionSchema = z.object({
  claim_id: z.string().min(1, 'Claim ID is required'),
  patient_id: z.string().optional(),
  provider_npi: z.string().optional(),
  date_of_service: z.string().optional(),
  claim_type: z.enum(['professional', 'institutional']).optional(),
  billed_amount: z.number().nonnegative().optional(),
  total_amount: z.number().nonnegative().optional(),
  diagnosis_codes: z.array(z.string()).optional(),
  items: z.array(ClaimItemSchema).min(1, 'At least one claim item is required'),
  provider: z.object({
    npi: z.string(),
    specialty: z.string().optional(),
  }).optional(),
  member: z.object({
    age: z.number().int().nonnegative(),
    gender: z.enum(['M', 'F']),
  }).optional(),
});

export type ValidatedClaimSubmission = z.infer<typeof ClaimSubmissionSchema>;

/**
 * Validate claim JSON and return parsed result or error
 */
export function validateClaimJson(jsonString: string): {
  success: true;
  data: ValidatedClaimSubmission;
} | {
  success: false;
  error: string;
} {
  // First, try to parse JSON
  let parsed: unknown;
  try {
    parsed = JSON.parse(jsonString);
  } catch {
    return {
      success: false,
      error: 'Invalid JSON format. Please check your syntax.',
    };
  }

  // Then validate against schema
  const result = ClaimSubmissionSchema.safeParse(parsed);

  if (!result.success) {
    // Format Zod errors into user-friendly message
    const errors = result.error.issues.map((issue) => {
      const path = issue.path.join('.');
      return path ? `${path}: ${issue.message}` : issue.message;
    });
    return {
      success: false,
      error: errors.join('; '),
    };
  }

  return {
    success: true,
    data: result.data,
  };
}
