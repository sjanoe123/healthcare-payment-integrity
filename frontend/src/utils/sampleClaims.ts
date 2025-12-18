import type { ClaimSubmission } from '@/api/types';

export const sampleClaims: { name: string; description: string; claim: ClaimSubmission }[] = [
  {
    name: 'Clean Claim',
    description: 'Standard office visit with no issues',
    claim: {
      claim_id: 'DEMO-CLEAN-001',
      patient_id: 'PT-9999',
      provider_npi: '1234567890',
      date_of_service: new Date().toISOString().split('T')[0],
      claim_type: 'professional',
      items: [
        {
          procedure_code: '99213',
          diagnosis_code: 'J06.9',
          quantity: 1,
          line_amount: 120.00,
        },
      ],
      total_amount: 120.00,
    },
  },
  {
    name: 'NCCI Violation',
    description: 'Unbundled CPT codes that should be combined',
    claim: {
      claim_id: 'DEMO-NCCI-001',
      patient_id: 'PT-8888',
      provider_npi: '1234567890',
      date_of_service: new Date().toISOString().split('T')[0],
      claim_type: 'professional',
      items: [
        {
          procedure_code: '99214',
          diagnosis_code: 'J06.9',
          quantity: 1,
          line_amount: 150.00,
        },
        {
          procedure_code: '99215',
          diagnosis_code: 'J06.9',
          quantity: 1,
          line_amount: 200.00,
        },
        {
          procedure_code: '99213',
          diagnosis_code: 'J18.9',
          quantity: 1,
          line_amount: 120.00,
        },
      ],
      total_amount: 470.00,
    },
  },
  {
    name: 'Excluded Provider',
    description: 'Provider on OIG LEIE exclusion list',
    claim: {
      claim_id: 'DEMO-OIG-001',
      patient_id: 'PT-7777',
      provider_npi: '1003000126',
      date_of_service: new Date().toISOString().split('T')[0],
      claim_type: 'professional',
      items: [
        {
          procedure_code: '99214',
          diagnosis_code: 'M54.5',
          quantity: 1,
          line_amount: 150.00,
        },
      ],
      total_amount: 150.00,
    },
  },
  {
    name: 'High-Value Suspicious',
    description: 'Multiple E/M codes with high amount',
    claim: {
      claim_id: 'DEMO-RISK-001',
      patient_id: 'PT-6666',
      provider_npi: '1234567890',
      date_of_service: new Date().toISOString().split('T')[0],
      claim_type: 'professional',
      items: [
        {
          procedure_code: '99215',
          diagnosis_code: 'I10',
          quantity: 1,
          line_amount: 200.00,
        },
        {
          procedure_code: '99214',
          diagnosis_code: 'E11.9',
          quantity: 1,
          line_amount: 150.00,
        },
        {
          procedure_code: '99213',
          diagnosis_code: 'J45.909',
          quantity: 1,
          line_amount: 120.00,
        },
        {
          procedure_code: '90834',
          diagnosis_code: 'F32.9',
          quantity: 1,
          line_amount: 135.00,
        },
      ],
      total_amount: 605.00,
    },
  },
  {
    name: 'MUE Violation',
    description: 'Quantity exceeds maximum units of service',
    claim: {
      claim_id: 'DEMO-MUE-001',
      patient_id: 'PT-5555',
      provider_npi: '1234567890',
      date_of_service: new Date().toISOString().split('T')[0],
      claim_type: 'professional',
      items: [
        {
          procedure_code: '99214',
          diagnosis_code: 'M54.5',
          quantity: 5,
          line_amount: 750.00,
        },
      ],
      total_amount: 750.00,
    },
  },
];
