import { describe, it, expect } from 'vitest';
import { validateClaimJson, ClaimSubmissionSchema, ClaimItemSchema } from './validation';

describe('ClaimItemSchema', () => {
  it('validates a valid claim item', () => {
    const validItem = {
      procedure_code: '99213',
      quantity: 1,
      line_amount: 100.0,
    };
    const result = ClaimItemSchema.safeParse(validItem);
    expect(result.success).toBe(true);
  });

  it('rejects empty procedure code', () => {
    const invalidItem = {
      procedure_code: '',
      quantity: 1,
      line_amount: 100.0,
    };
    const result = ClaimItemSchema.safeParse(invalidItem);
    expect(result.success).toBe(false);
  });

  it('rejects negative quantity', () => {
    const invalidItem = {
      procedure_code: '99213',
      quantity: -1,
      line_amount: 100.0,
    };
    const result = ClaimItemSchema.safeParse(invalidItem);
    expect(result.success).toBe(false);
  });

  it('rejects negative line amount', () => {
    const invalidItem = {
      procedure_code: '99213',
      quantity: 1,
      line_amount: -50.0,
    };
    const result = ClaimItemSchema.safeParse(invalidItem);
    expect(result.success).toBe(false);
  });

  it('accepts optional fields', () => {
    const itemWithOptional = {
      procedure_code: '99213',
      diagnosis_code: 'J06.9',
      quantity: 1,
      line_amount: 100.0,
      modifier: '25',
    };
    const result = ClaimItemSchema.safeParse(itemWithOptional);
    expect(result.success).toBe(true);
  });
});

describe('ClaimSubmissionSchema', () => {
  const validClaim = {
    claim_id: 'CLM-001',
    items: [
      {
        procedure_code: '99213',
        quantity: 1,
        line_amount: 100.0,
      },
    ],
  };

  it('validates a minimal valid claim', () => {
    const result = ClaimSubmissionSchema.safeParse(validClaim);
    expect(result.success).toBe(true);
  });

  it('rejects missing claim_id', () => {
    const invalidClaim = { ...validClaim, claim_id: '' };
    const result = ClaimSubmissionSchema.safeParse(invalidClaim);
    expect(result.success).toBe(false);
  });

  it('rejects empty items array', () => {
    const invalidClaim = { ...validClaim, items: [] };
    const result = ClaimSubmissionSchema.safeParse(invalidClaim);
    expect(result.success).toBe(false);
  });

  it('validates a complete claim with all fields', () => {
    const completeClaim = {
      claim_id: 'CLM-002',
      patient_id: 'PAT-001',
      provider_npi: '1234567890',
      date_of_service: '2024-01-15',
      claim_type: 'professional' as const,
      billed_amount: 500.0,
      total_amount: 500.0,
      diagnosis_codes: ['J06.9', 'R05'],
      items: [
        {
          procedure_code: '99214',
          diagnosis_code: 'J06.9',
          quantity: 1,
          line_amount: 300.0,
          modifier: '25',
        },
        {
          procedure_code: '99213',
          quantity: 1,
          line_amount: 200.0,
        },
      ],
      provider: {
        npi: '1234567890',
        specialty: 'Internal Medicine',
      },
      member: {
        age: 45,
        gender: 'M' as const,
      },
    };
    const result = ClaimSubmissionSchema.safeParse(completeClaim);
    expect(result.success).toBe(true);
  });

  it('rejects invalid claim_type', () => {
    const invalidClaim = { ...validClaim, claim_type: 'invalid' };
    const result = ClaimSubmissionSchema.safeParse(invalidClaim);
    expect(result.success).toBe(false);
  });

  it('rejects invalid gender', () => {
    const invalidClaim = {
      ...validClaim,
      member: { age: 30, gender: 'X' },
    };
    const result = ClaimSubmissionSchema.safeParse(invalidClaim);
    expect(result.success).toBe(false);
  });
});

describe('validateClaimJson', () => {
  it('returns success for valid JSON', () => {
    const validJson = JSON.stringify({
      claim_id: 'CLM-001',
      items: [{ procedure_code: '99213', quantity: 1, line_amount: 100 }],
    });
    const result = validateClaimJson(validJson);
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.claim_id).toBe('CLM-001');
    }
  });

  it('returns error for invalid JSON syntax', () => {
    const invalidJson = '{ claim_id: "CLM-001" }'; // Missing quotes around key
    const result = validateClaimJson(invalidJson);
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error).toContain('Invalid JSON');
    }
  });

  it('returns error for valid JSON but invalid schema', () => {
    const invalidClaim = JSON.stringify({
      claim_id: '',
      items: [],
    });
    const result = validateClaimJson(invalidClaim);
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error).toBeTruthy();
    }
  });

  it('formats validation errors with field paths', () => {
    const invalidClaim = JSON.stringify({
      claim_id: 'CLM-001',
      items: [{ procedure_code: '', quantity: -1, line_amount: 100 }],
    });
    const result = validateClaimJson(invalidClaim);
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error).toContain('items');
    }
  });

  it('handles non-object JSON', () => {
    const arrayJson = JSON.stringify([1, 2, 3]);
    const result = validateClaimJson(arrayJson);
    expect(result.success).toBe(false);
  });

  it('handles null JSON', () => {
    const nullJson = 'null';
    const result = validateClaimJson(nullJson);
    expect(result.success).toBe(false);
  });
});
