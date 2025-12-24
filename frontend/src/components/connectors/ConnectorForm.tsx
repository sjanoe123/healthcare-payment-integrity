import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useCreateConnector, useTestConnection } from '../../api/hooks/useConnectors';

interface ConnectorFormProps {
  onClose: () => void;
  onSuccess?: () => void;
}

type Step = 'type' | 'config' | 'test' | 'schedule';

interface FormData {
  name: string;
  connector_type: string;
  subtype: string;
  data_type: string;
  // Database fields
  host: string;
  port: number;
  database: string;
  username: string;
  password: string;
  ssl_mode: string;
  schema_name: string;
  table: string;
  query: string;
  watermark_column: string;
  // S3 fields
  bucket: string;
  region: string;
  access_key_id: string;
  secret_access_key: string;
  endpoint_url: string;
  prefix: string;
  // SFTP fields
  private_key: string;
  private_key_passphrase: string;
  remote_path: string;
  // File common fields
  path_pattern: string;
  file_format: string;
  delimiter: string;
  has_header: boolean;
  archive_processed: boolean;
  archive_path: string;
  // API fields
  base_url: string;
  api_endpoint: string;
  auth_type: string;
  api_key: string;
  api_key_header: string;
  bearer_token: string;
  oauth2_token_url: string;
  oauth2_client_id: string;
  oauth2_client_secret: string;
  oauth2_scope: string;
  pagination_type: string;
  data_path: string;
  rate_limit: number;
  timeout: number;
  verify_ssl: boolean;
  // FHIR fields
  resource_types: string[];
  // Sync fields
  sync_schedule: string;
  sync_mode: string;
  batch_size: number;
}

const CONNECTOR_TYPES = [
  {
    type: 'database',
    label: 'Database',
    icon: 'M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4',
    subtypes: [
      { value: 'postgresql', label: 'PostgreSQL', port: 5432 },
      { value: 'mysql', label: 'MySQL', port: 3306 },
      { value: 'sqlserver', label: 'SQL Server', port: 1433 },
    ],
  },
  {
    type: 'api',
    label: 'API',
    icon: 'M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z',
    subtypes: [
      { value: 'rest', label: 'REST API', port: 443 },
      { value: 'fhir', label: 'HL7 FHIR', port: 443 },
    ],
  },
  {
    type: 'file',
    label: 'File System',
    icon: 'M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z',
    subtypes: [
      { value: 's3', label: 'Amazon S3', port: 443 },
      { value: 'sftp', label: 'SFTP', port: 22 },
      { value: 'azure_blob', label: 'Azure Blob', port: 443 },
    ],
  },
];

const DATA_TYPES = [
  { value: 'claims', label: 'Claims', description: 'Healthcare claims (837P/I)' },
  { value: 'eligibility', label: 'Eligibility', description: 'Member eligibility data' },
  { value: 'providers', label: 'Providers', description: 'Provider/facility data' },
  { value: 'reference', label: 'Reference', description: 'NCCI, LCD, MPFS data' },
];

const SSL_MODES = [
  { value: 'disable', label: 'Disable' },
  { value: 'prefer', label: 'Prefer (default)' },
  { value: 'require', label: 'Require' },
  { value: 'verify-ca', label: 'Verify CA' },
  { value: 'verify-full', label: 'Verify Full' },
];

const FILE_FORMATS = [
  { value: 'csv', label: 'CSV' },
  { value: 'json', label: 'JSON' },
  { value: 'edi_837', label: 'EDI 837 (auto-detect)' },
  { value: 'edi_837p', label: 'EDI 837P (Professional)' },
  { value: 'edi_837i', label: 'EDI 837I (Institutional)' },
];

const AWS_REGIONS = [
  { value: 'us-east-1', label: 'US East (N. Virginia)' },
  { value: 'us-east-2', label: 'US East (Ohio)' },
  { value: 'us-west-1', label: 'US West (N. California)' },
  { value: 'us-west-2', label: 'US West (Oregon)' },
  { value: 'eu-west-1', label: 'EU (Ireland)' },
  { value: 'eu-central-1', label: 'EU (Frankfurt)' },
  { value: 'ap-northeast-1', label: 'Asia Pacific (Tokyo)' },
  { value: 'ap-southeast-1', label: 'Asia Pacific (Singapore)' },
];

const AUTH_TYPES = [
  { value: 'none', label: 'None' },
  { value: 'api_key', label: 'API Key' },
  { value: 'basic', label: 'Basic Auth' },
  { value: 'bearer', label: 'Bearer Token' },
  { value: 'oauth2', label: 'OAuth2' },
];

const PAGINATION_TYPES = [
  { value: 'none', label: 'None (single request)' },
  { value: 'offset', label: 'Offset-based' },
  { value: 'page', label: 'Page number' },
  { value: 'cursor', label: 'Cursor-based' },
  { value: 'link_header', label: 'Link header (RFC 5988)' },
];

const FHIR_RESOURCES = [
  { value: 'Claim', label: 'Claim' },
  { value: 'ExplanationOfBenefit', label: 'Explanation of Benefit' },
  { value: 'Coverage', label: 'Coverage' },
  { value: 'Patient', label: 'Patient' },
  { value: 'Practitioner', label: 'Practitioner' },
  { value: 'Organization', label: 'Organization' },
  { value: 'Location', label: 'Location' },
];

export function ConnectorForm({ onClose, onSuccess }: ConnectorFormProps) {
  const [step, setStep] = useState<Step>('type');
  const [formData, setFormData] = useState<FormData>({
    name: '',
    connector_type: '',
    subtype: '',
    data_type: 'claims',
    // Database
    host: 'localhost',
    port: 5432,
    database: '',
    username: '',
    password: '',
    ssl_mode: 'prefer',
    schema_name: 'public',
    table: '',
    query: '',
    watermark_column: '',
    // S3
    bucket: '',
    region: 'us-east-1',
    access_key_id: '',
    secret_access_key: '',
    endpoint_url: '',
    prefix: '',
    // SFTP
    private_key: '',
    private_key_passphrase: '',
    remote_path: '/',
    // File common
    path_pattern: '*',
    file_format: 'csv',
    delimiter: ',',
    has_header: true,
    archive_processed: false,
    archive_path: '',
    // API
    base_url: '',
    api_endpoint: '/',
    auth_type: 'none',
    api_key: '',
    api_key_header: 'X-API-Key',
    bearer_token: '',
    oauth2_token_url: '',
    oauth2_client_id: '',
    oauth2_client_secret: '',
    oauth2_scope: '',
    pagination_type: 'none',
    data_path: '',
    rate_limit: 10,
    timeout: 30,
    verify_ssl: true,
    // FHIR
    resource_types: ['Claim'],
    // Sync
    sync_schedule: '',
    sync_mode: 'incremental',
    batch_size: 1000,
  });
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);
  const [createdConnectorId, setCreatedConnectorId] = useState<string | null>(null);

  const createConnector = useCreateConnector();
  const testConnection = useTestConnection();

  const updateField = <K extends keyof FormData>(field: K, value: FormData[K]) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
  };

  const selectType = (type: string, subtype: string, port: number) => {
    updateField('connector_type', type);
    updateField('subtype', subtype);
    updateField('port', port);
    setStep('config');
  };

  const buildConnectionConfig = () => {
    if (formData.connector_type === 'database') {
      return {
        host: formData.host,
        port: formData.port,
        database: formData.database,
        username: formData.username,
        password: formData.password,
        ssl_mode: formData.ssl_mode,
        schema_name: formData.schema_name,
        table: formData.table || undefined,
        query: formData.query || undefined,
        watermark_column: formData.watermark_column || undefined,
      };
    } else if (formData.connector_type === 'file') {
      if (formData.subtype === 's3') {
        return {
          bucket: formData.bucket,
          region: formData.region,
          access_key_id: formData.access_key_id || undefined,
          secret_access_key: formData.secret_access_key || undefined,
          endpoint_url: formData.endpoint_url || undefined,
          prefix: formData.prefix || '',
          path_pattern: formData.path_pattern || '*',
          file_format: formData.file_format,
          delimiter: formData.delimiter,
          has_header: formData.has_header,
          archive_processed: formData.archive_processed,
          archive_path: formData.archive_path || undefined,
        };
      } else if (formData.subtype === 'sftp') {
        return {
          host: formData.host,
          port: formData.port,
          username: formData.username,
          password: formData.password || undefined,
          private_key: formData.private_key || undefined,
          private_key_passphrase: formData.private_key_passphrase || undefined,
          remote_path: formData.remote_path || '/',
          path_pattern: formData.path_pattern || '*',
          file_format: formData.file_format,
          delimiter: formData.delimiter,
          has_header: formData.has_header,
          archive_processed: formData.archive_processed,
          archive_path: formData.archive_path || undefined,
        };
      }
    }
    // API connectors
    if (formData.connector_type === 'api') {
      const config: Record<string, unknown> = {
        base_url: formData.base_url,
        endpoint: formData.api_endpoint || '/',
        auth_type: formData.auth_type,
        timeout: formData.timeout,
        rate_limit: formData.rate_limit,
        verify_ssl: formData.verify_ssl,
      };

      // Auth-specific fields
      if (formData.auth_type === 'api_key') {
        config.api_key = formData.api_key;
        config.api_key_header = formData.api_key_header;
      } else if (formData.auth_type === 'basic') {
        config.username = formData.username;
        config.password = formData.password;
      } else if (formData.auth_type === 'bearer') {
        config.bearer_token = formData.bearer_token;
      } else if (formData.auth_type === 'oauth2') {
        config.oauth2_config = {
          token_url: formData.oauth2_token_url,
          client_id: formData.oauth2_client_id,
          client_secret: formData.oauth2_client_secret,
          scope: formData.oauth2_scope || undefined,
          grant_type: 'client_credentials',
        };
      }

      if (formData.subtype === 'rest') {
        config.pagination_type = formData.pagination_type;
        config.data_path = formData.data_path || undefined;
      } else if (formData.subtype === 'fhir') {
        config.resource_types = formData.resource_types;
      }

      return config;
    }

    // Default
    return {
      host: formData.host,
      port: formData.port,
      username: formData.username,
      password: formData.password,
    };
  };

  const handleTest = async () => {
    if (!createdConnectorId) {
      // Create connector first to test
      try {
        const connector = await createConnector.mutateAsync({
          name: formData.name || `Test ${formData.subtype} connector`,
          connector_type: formData.connector_type,
          subtype: formData.subtype,
          data_type: formData.data_type,
          connection_config: buildConnectionConfig(),
          sync_mode: formData.sync_mode,
          batch_size: formData.batch_size,
        });
        setCreatedConnectorId(connector.id);

        // Now test
        const result = await testConnection.mutateAsync(connector.id);
        setTestResult({ success: result.success, message: result.message });

        if (result.success) {
          setStep('schedule');
        }
      } catch (error) {
        setTestResult({
          success: false,
          message: error instanceof Error ? error.message : 'Failed to create connector',
        });
      }
    } else {
      // Test existing connector
      try {
        const result = await testConnection.mutateAsync(createdConnectorId);
        setTestResult({ success: result.success, message: result.message });

        if (result.success) {
          setStep('schedule');
        }
      } catch (error) {
        setTestResult({
          success: false,
          message: error instanceof Error ? error.message : 'Connection test failed',
        });
      }
    }
  };

  const handleComplete = () => {
    onSuccess?.();
    onClose();
  };

  const canProceedFromConfig = () => {
    if (!formData.name) return false;

    if (formData.connector_type === 'database') {
      return formData.host && formData.port && formData.database && formData.username;
    } else if (formData.connector_type === 'file') {
      if (formData.subtype === 's3') {
        return !!formData.bucket;
      } else if (formData.subtype === 'sftp') {
        return formData.host && formData.username;
      }
    } else if (formData.connector_type === 'api') {
      if (!formData.base_url) return false;
      // Check auth requirements
      if (formData.auth_type === 'api_key' && !formData.api_key) return false;
      if (formData.auth_type === 'basic' && (!formData.username || !formData.password)) return false;
      if (formData.auth_type === 'bearer' && !formData.bearer_token) return false;
      if (formData.auth_type === 'oauth2' && (!formData.oauth2_token_url || !formData.oauth2_client_id || !formData.oauth2_client_secret)) return false;
      return true;
    }
    return true;
  };

  const renderDatabaseConfig = () => (
    <>
      <div className="grid grid-cols-3 gap-4">
        <div className="col-span-2">
          <label className="block text-sm font-medium text-gray-700 mb-1">Host *</label>
          <input
            type="text"
            value={formData.host}
            onChange={(e) => updateField('host', e.target.value)}
            placeholder="localhost"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Port *</label>
          <input
            type="number"
            value={formData.port}
            onChange={(e) => updateField('port', parseInt(e.target.value))}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
          />
        </div>
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Database *</label>
        <input
          type="text"
          value={formData.database}
          onChange={(e) => updateField('database', e.target.value)}
          placeholder="claims_db"
          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
        />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Username *</label>
          <input
            type="text"
            value={formData.username}
            onChange={(e) => updateField('username', e.target.value)}
            placeholder="db_user"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Password</label>
          <input
            type="password"
            value={formData.password}
            onChange={(e) => updateField('password', e.target.value)}
            placeholder="••••••••"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
          />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">SSL Mode</label>
          <select
            value={formData.ssl_mode}
            onChange={(e) => updateField('ssl_mode', e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
          >
            {SSL_MODES.map((mode) => (
              <option key={mode.value} value={mode.value}>
                {mode.label}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Schema</label>
          <input
            type="text"
            value={formData.schema_name}
            onChange={(e) => updateField('schema_name', e.target.value)}
            placeholder="public"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
          />
        </div>
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Table (optional)</label>
        <input
          type="text"
          value={formData.table}
          onChange={(e) => updateField('table', e.target.value)}
          placeholder="claims"
          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
        />
      </div>
    </>
  );

  const renderS3Config = () => (
    <>
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Bucket Name *</label>
        <input
          type="text"
          value={formData.bucket}
          onChange={(e) => updateField('bucket', e.target.value)}
          placeholder="my-claims-bucket"
          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">AWS Region</label>
        <select
          value={formData.region}
          onChange={(e) => updateField('region', e.target.value)}
          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
        >
          {AWS_REGIONS.map((r) => (
            <option key={r.value} value={r.value}>
              {r.label}
            </option>
          ))}
        </select>
        <p className="text-xs text-gray-500 mt-1">Leave empty for IAM role-based authentication</p>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Access Key ID</label>
          <input
            type="text"
            value={formData.access_key_id}
            onChange={(e) => updateField('access_key_id', e.target.value)}
            placeholder="AKIA..."
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Secret Access Key</label>
          <input
            type="password"
            value={formData.secret_access_key}
            onChange={(e) => updateField('secret_access_key', e.target.value)}
            placeholder="••••••••"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
          />
        </div>
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Custom Endpoint URL</label>
        <input
          type="text"
          value={formData.endpoint_url}
          onChange={(e) => updateField('endpoint_url', e.target.value)}
          placeholder="https://minio.example.com"
          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
        />
        <p className="text-xs text-gray-500 mt-1">For S3-compatible services like MinIO</p>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Path Prefix</label>
          <input
            type="text"
            value={formData.prefix}
            onChange={(e) => updateField('prefix', e.target.value)}
            placeholder="claims/incoming/"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">File Pattern</label>
          <input
            type="text"
            value={formData.path_pattern}
            onChange={(e) => updateField('path_pattern', e.target.value)}
            placeholder="*.csv"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
          />
        </div>
      </div>

      {renderFileFormatConfig()}
    </>
  );

  const renderSFTPConfig = () => (
    <>
      <div className="grid grid-cols-3 gap-4">
        <div className="col-span-2">
          <label className="block text-sm font-medium text-gray-700 mb-1">Host *</label>
          <input
            type="text"
            value={formData.host}
            onChange={(e) => updateField('host', e.target.value)}
            placeholder="sftp.example.com"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Port</label>
          <input
            type="number"
            value={formData.port}
            onChange={(e) => updateField('port', parseInt(e.target.value))}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
          />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Username *</label>
          <input
            type="text"
            value={formData.username}
            onChange={(e) => updateField('username', e.target.value)}
            placeholder="sftp_user"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Password</label>
          <input
            type="password"
            value={formData.password}
            onChange={(e) => updateField('password', e.target.value)}
            placeholder="••••••••"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
          />
        </div>
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Private Key (PEM format)
        </label>
        <textarea
          value={formData.private_key}
          onChange={(e) => updateField('private_key', e.target.value)}
          placeholder="-----BEGIN RSA PRIVATE KEY-----&#10;...&#10;-----END RSA PRIVATE KEY-----"
          rows={4}
          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 font-mono text-sm"
        />
        <p className="text-xs text-gray-500 mt-1">Use instead of password for key-based auth</p>
      </div>

      {formData.private_key && (
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Key Passphrase</label>
          <input
            type="password"
            value={formData.private_key_passphrase}
            onChange={(e) => updateField('private_key_passphrase', e.target.value)}
            placeholder="••••••••"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
          />
        </div>
      )}

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Remote Path</label>
          <input
            type="text"
            value={formData.remote_path}
            onChange={(e) => updateField('remote_path', e.target.value)}
            placeholder="/claims/incoming"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">File Pattern</label>
          <input
            type="text"
            value={formData.path_pattern}
            onChange={(e) => updateField('path_pattern', e.target.value)}
            placeholder="*.edi"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
          />
        </div>
      </div>

      {renderFileFormatConfig()}
    </>
  );

  const renderFileFormatConfig = () => (
    <>
      <div className="border-t border-gray-200 pt-4 mt-2">
        <h4 className="text-sm font-medium text-gray-900 mb-3">File Format Settings</h4>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">File Format</label>
            <select
              value={formData.file_format}
              onChange={(e) => updateField('file_format', e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
            >
              {FILE_FORMATS.map((f) => (
                <option key={f.value} value={f.value}>
                  {f.label}
                </option>
              ))}
            </select>
          </div>

          {formData.file_format === 'csv' && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Delimiter</label>
              <select
                value={formData.delimiter}
                onChange={(e) => updateField('delimiter', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
              >
                <option value=",">Comma (,)</option>
                <option value=";">Semicolon (;)</option>
                <option value="\t">Tab</option>
                <option value="|">Pipe (|)</option>
              </select>
            </div>
          )}
        </div>

        {formData.file_format === 'csv' && (
          <div className="mt-3">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={formData.has_header}
                onChange={(e) => updateField('has_header', e.target.checked)}
                className="w-4 h-4 text-indigo-600 border-gray-300 rounded focus:ring-indigo-500"
              />
              <span className="text-sm text-gray-700">File has header row</span>
            </label>
          </div>
        )}

        <div className="mt-3">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={formData.archive_processed}
              onChange={(e) => updateField('archive_processed', e.target.checked)}
              className="w-4 h-4 text-indigo-600 border-gray-300 rounded focus:ring-indigo-500"
            />
            <span className="text-sm text-gray-700">Archive files after processing</span>
          </label>
        </div>

        {formData.archive_processed && (
          <div className="mt-3">
            <label className="block text-sm font-medium text-gray-700 mb-1">Archive Path</label>
            <input
              type="text"
              value={formData.archive_path}
              onChange={(e) => updateField('archive_path', e.target.value)}
              placeholder={formData.subtype === 's3' ? 'archive/processed/' : '/archive/processed'}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
            />
          </div>
        )}
      </div>
    </>
  );

  const renderAuthConfig = () => (
    <>
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Authentication</label>
        <select
          value={formData.auth_type}
          onChange={(e) => updateField('auth_type', e.target.value)}
          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
        >
          {AUTH_TYPES.map((t) => (
            <option key={t.value} value={t.value}>{t.label}</option>
          ))}
        </select>
      </div>

      {formData.auth_type === 'api_key' && (
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">API Key *</label>
            <input
              type="password"
              value={formData.api_key}
              onChange={(e) => updateField('api_key', e.target.value)}
              placeholder="Your API key"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Header Name</label>
            <input
              type="text"
              value={formData.api_key_header}
              onChange={(e) => updateField('api_key_header', e.target.value)}
              placeholder="X-API-Key"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
            />
          </div>
        </div>
      )}

      {formData.auth_type === 'basic' && (
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Username *</label>
            <input
              type="text"
              value={formData.username}
              onChange={(e) => updateField('username', e.target.value)}
              placeholder="username"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Password *</label>
            <input
              type="password"
              value={formData.password}
              onChange={(e) => updateField('password', e.target.value)}
              placeholder="••••••••"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
            />
          </div>
        </div>
      )}

      {formData.auth_type === 'bearer' && (
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Bearer Token *</label>
          <input
            type="password"
            value={formData.bearer_token}
            onChange={(e) => updateField('bearer_token', e.target.value)}
            placeholder="Your bearer token"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
          />
        </div>
      )}

      {formData.auth_type === 'oauth2' && (
        <>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Token URL *</label>
            <input
              type="text"
              value={formData.oauth2_token_url}
              onChange={(e) => updateField('oauth2_token_url', e.target.value)}
              placeholder="https://auth.example.com/oauth/token"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Client ID *</label>
              <input
                type="text"
                value={formData.oauth2_client_id}
                onChange={(e) => updateField('oauth2_client_id', e.target.value)}
                placeholder="client_id"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Client Secret *</label>
              <input
                type="password"
                value={formData.oauth2_client_secret}
                onChange={(e) => updateField('oauth2_client_secret', e.target.value)}
                placeholder="••••••••"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
              />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Scope</label>
            <input
              type="text"
              value={formData.oauth2_scope}
              onChange={(e) => updateField('oauth2_scope', e.target.value)}
              placeholder="system/*.read"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
            />
          </div>
        </>
      )}
    </>
  );

  const renderRESTConfig = () => (
    <>
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Base URL *</label>
        <input
          type="text"
          value={formData.base_url}
          onChange={(e) => updateField('base_url', e.target.value)}
          placeholder="https://api.example.com"
          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Data Endpoint</label>
        <input
          type="text"
          value={formData.api_endpoint}
          onChange={(e) => updateField('api_endpoint', e.target.value)}
          placeholder="/v1/claims"
          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
        />
      </div>

      {renderAuthConfig()}

      <div className="border-t border-gray-200 pt-4 mt-2">
        <h4 className="text-sm font-medium text-gray-900 mb-3">Response Settings</h4>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Pagination Type</label>
            <select
              value={formData.pagination_type}
              onChange={(e) => updateField('pagination_type', e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
            >
              {PAGINATION_TYPES.map((t) => (
                <option key={t.value} value={t.value}>{t.label}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Data Path</label>
            <input
              type="text"
              value={formData.data_path}
              onChange={(e) => updateField('data_path', e.target.value)}
              placeholder="data.items"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
            />
            <p className="text-xs text-gray-500 mt-1">JSON path to records array</p>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-4 mt-3">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Timeout (sec)</label>
            <input
              type="number"
              value={formData.timeout}
              onChange={(e) => updateField('timeout', parseInt(e.target.value))}
              min={5}
              max={300}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Rate Limit</label>
            <input
              type="number"
              value={formData.rate_limit}
              onChange={(e) => updateField('rate_limit', parseInt(e.target.value))}
              min={1}
              max={100}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
            />
            <p className="text-xs text-gray-500 mt-1">req/sec</p>
          </div>
          <div className="flex items-end pb-2">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={formData.verify_ssl}
                onChange={(e) => updateField('verify_ssl', e.target.checked)}
                className="w-4 h-4 text-indigo-600 border-gray-300 rounded focus:ring-indigo-500"
              />
              <span className="text-sm text-gray-700">Verify SSL</span>
            </label>
          </div>
        </div>
      </div>
    </>
  );

  const renderFHIRConfig = () => (
    <>
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">FHIR Server URL *</label>
        <input
          type="text"
          value={formData.base_url}
          onChange={(e) => updateField('base_url', e.target.value)}
          placeholder="https://fhir.example.com/r4"
          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Resource Types</label>
        <div className="grid grid-cols-2 gap-2 mt-1">
          {FHIR_RESOURCES.map((r) => (
            <label key={r.value} className="flex items-center gap-2 cursor-pointer p-2 border border-gray-200 rounded-lg hover:bg-gray-50">
              <input
                type="checkbox"
                checked={formData.resource_types.includes(r.value)}
                onChange={(e) => {
                  if (e.target.checked) {
                    updateField('resource_types', [...formData.resource_types, r.value]);
                  } else {
                    updateField('resource_types', formData.resource_types.filter(v => v !== r.value));
                  }
                }}
                className="w-4 h-4 text-indigo-600 border-gray-300 rounded focus:ring-indigo-500"
              />
              <span className="text-sm text-gray-700">{r.label}</span>
            </label>
          ))}
        </div>
      </div>

      {renderAuthConfig()}

      <div className="border-t border-gray-200 pt-4 mt-2">
        <h4 className="text-sm font-medium text-gray-900 mb-3">Connection Settings</h4>

        <div className="grid grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Timeout (sec)</label>
            <input
              type="number"
              value={formData.timeout}
              onChange={(e) => updateField('timeout', parseInt(e.target.value))}
              min={10}
              max={300}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Rate Limit</label>
            <input
              type="number"
              value={formData.rate_limit}
              onChange={(e) => updateField('rate_limit', parseInt(e.target.value))}
              min={1}
              max={50}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
            />
            <p className="text-xs text-gray-500 mt-1">req/sec</p>
          </div>
          <div className="flex items-end pb-2">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={formData.verify_ssl}
                onChange={(e) => updateField('verify_ssl', e.target.checked)}
                className="w-4 h-4 text-indigo-600 border-gray-300 rounded focus:ring-indigo-500"
              />
              <span className="text-sm text-gray-700">Verify SSL</span>
            </label>
          </div>
        </div>
      </div>
    </>
  );

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4"
      onClick={onClose}
    >
      <motion.div
        initial={{ scale: 0.9, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        exit={{ scale: 0.9, opacity: 0 }}
        className="bg-white rounded-xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
          <div>
            <h2 className="text-xl font-bold text-gray-900">Add Data Source Connector</h2>
            <p className="text-sm text-gray-500 mt-1">
              {step === 'type' && 'Select connector type'}
              {step === 'config' && 'Configure connection settings'}
              {step === 'test' && 'Test your connection'}
              {step === 'schedule' && 'Configure sync schedule'}
            </p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Progress Steps */}
        <div className="px-6 py-3 bg-gray-50 border-b border-gray-200">
          <div className="flex items-center justify-between">
            {['type', 'config', 'test', 'schedule'].map((s, i) => (
              <div key={s} className="flex items-center">
                <div
                  className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${
                    step === s
                      ? 'bg-indigo-600 text-white'
                      : ['type', 'config', 'test', 'schedule'].indexOf(step) > i
                      ? 'bg-green-500 text-white'
                      : 'bg-gray-200 text-gray-600'
                  }`}
                >
                  {['type', 'config', 'test', 'schedule'].indexOf(step) > i ? (
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                  ) : (
                    i + 1
                  )}
                </div>
                {i < 3 && (
                  <div
                    className={`w-16 h-1 mx-2 ${
                      ['type', 'config', 'test', 'schedule'].indexOf(step) > i
                        ? 'bg-green-500'
                        : 'bg-gray-200'
                    }`}
                  />
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Content */}
        <div className="p-6 overflow-y-auto max-h-[60vh]">
          <AnimatePresence mode="wait">
            {/* Step 1: Select Type */}
            {step === 'type' && (
              <motion.div
                key="type"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                className="space-y-4"
              >
                {CONNECTOR_TYPES.map((ct) => (
                  <div key={ct.type} className="border border-gray-200 rounded-lg p-4">
                    <div className="flex items-center gap-3 mb-3">
                      <div className="p-2 bg-indigo-100 rounded-lg">
                        <svg className="w-5 h-5 text-indigo-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={ct.icon} />
                        </svg>
                      </div>
                      <span className="font-medium text-gray-900">{ct.label}</span>
                    </div>
                    <div className="grid grid-cols-3 gap-2">
                      {ct.subtypes.map((st) => (
                        <button
                          key={st.value}
                          onClick={() => selectType(ct.type, st.value, st.port)}
                          className="p-3 text-left rounded-lg border border-gray-200 hover:border-indigo-500 hover:bg-indigo-50 transition-colors"
                        >
                          <span className="font-medium text-gray-800 block">{st.label}</span>
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
              </motion.div>
            )}

            {/* Step 2: Configuration */}
            {step === 'config' && (
              <motion.div
                key="config"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                className="space-y-4"
              >
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Connector Name *</label>
                  <input
                    type="text"
                    value={formData.name}
                    onChange={(e) => updateField('name', e.target.value)}
                    placeholder={`e.g., Production ${formData.subtype.toUpperCase()} Claims`}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Data Type</label>
                  <select
                    value={formData.data_type}
                    onChange={(e) => updateField('data_type', e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
                  >
                    {DATA_TYPES.map((dt) => (
                      <option key={dt.value} value={dt.value}>
                        {dt.label} - {dt.description}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Render type-specific configuration */}
                {formData.connector_type === 'database' && renderDatabaseConfig()}
                {formData.connector_type === 'file' && formData.subtype === 's3' && renderS3Config()}
                {formData.connector_type === 'file' && formData.subtype === 'sftp' && renderSFTPConfig()}
                {formData.connector_type === 'api' && formData.subtype === 'rest' && renderRESTConfig()}
                {formData.connector_type === 'api' && formData.subtype === 'fhir' && renderFHIRConfig()}
              </motion.div>
            )}

            {/* Step 3: Test Connection */}
            {step === 'test' && (
              <motion.div
                key="test"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                className="text-center py-8"
              >
                {testConnection.isPending || createConnector.isPending ? (
                  <div>
                    <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600 mx-auto mb-4"></div>
                    <p className="text-gray-600">Testing connection...</p>
                  </div>
                ) : testResult ? (
                  <div>
                    <div
                      className={`w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-4 ${
                        testResult.success ? 'bg-green-100' : 'bg-red-100'
                      }`}
                    >
                      {testResult.success ? (
                        <svg className="w-8 h-8 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                        </svg>
                      ) : (
                        <svg className="w-8 h-8 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                      )}
                    </div>
                    <h3 className={`text-lg font-medium ${testResult.success ? 'text-green-700' : 'text-red-700'}`}>
                      {testResult.success ? 'Connection Successful!' : 'Connection Failed'}
                    </h3>
                    <p className="text-gray-600 mt-2">{testResult.message}</p>
                    {!testResult.success && (
                      <button
                        onClick={() => setStep('config')}
                        className="mt-4 text-indigo-600 hover:text-indigo-700 font-medium"
                      >
                        Edit Configuration
                      </button>
                    )}
                  </div>
                ) : (
                  <div>
                    <div className="w-16 h-16 rounded-full bg-indigo-100 flex items-center justify-center mx-auto mb-4">
                      <svg className="w-8 h-8 text-indigo-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                      </svg>
                    </div>
                    <h3 className="text-lg font-medium text-gray-900">Ready to Test</h3>
                    <p className="text-gray-600 mt-2">
                      Click the button below to test your connection settings.
                    </p>
                  </div>
                )}
              </motion.div>
            )}

            {/* Step 4: Schedule */}
            {step === 'schedule' && (
              <motion.div
                key="schedule"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                className="space-y-4"
              >
                <div className="bg-green-50 border border-green-200 rounded-lg p-4 mb-6">
                  <div className="flex items-center gap-2">
                    <svg className="w-5 h-5 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    <span className="text-green-800 font-medium">Connection verified successfully!</span>
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Sync Mode</label>
                  <select
                    value={formData.sync_mode}
                    onChange={(e) => updateField('sync_mode', e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
                  >
                    <option value="incremental">Incremental (recommended)</option>
                    <option value="full">Full sync</option>
                  </select>
                  <p className="text-sm text-gray-500 mt-1">
                    {formData.connector_type === 'file'
                      ? 'Incremental sync tracks processed files by modification time.'
                      : 'Incremental sync only fetches new/updated records using a watermark column.'}
                  </p>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Sync Schedule (cron)</label>
                  <input
                    type="text"
                    value={formData.sync_schedule}
                    onChange={(e) => updateField('sync_schedule', e.target.value)}
                    placeholder="0 */6 * * * (every 6 hours)"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
                  />
                  <p className="text-sm text-gray-500 mt-1">
                    Leave empty for manual sync only. Common: <code>0 0 * * *</code> (daily), <code>0 */6 * * *</code> (every 6h)
                  </p>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Batch Size</label>
                  <input
                    type="number"
                    value={formData.batch_size}
                    onChange={(e) => updateField('batch_size', parseInt(e.target.value))}
                    min={100}
                    max={10000}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
                  />
                  <p className="text-sm text-gray-500 mt-1">
                    Number of records to process per batch (100-10,000).
                  </p>
                </div>

                {formData.sync_mode === 'incremental' && formData.connector_type === 'database' && (
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Watermark Column</label>
                    <input
                      type="text"
                      value={formData.watermark_column}
                      onChange={(e) => updateField('watermark_column', e.target.value)}
                      placeholder="updated_at"
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
                    />
                    <p className="text-sm text-gray-500 mt-1">
                      Column used to track incremental updates (e.g., updated_at, modified_date).
                    </p>
                  </div>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-gray-200 flex items-center justify-between">
          <button
            onClick={() => {
              if (step === 'config') setStep('type');
              else if (step === 'test') setStep('config');
              else if (step === 'schedule') setStep('test');
            }}
            className={`px-4 py-2 text-gray-600 hover:text-gray-800 ${step === 'type' ? 'invisible' : ''}`}
          >
            Back
          </button>

          <div className="flex gap-2">
            <button onClick={onClose} className="px-4 py-2 text-gray-600 hover:text-gray-800">
              Cancel
            </button>

            {step === 'config' && (
              <button
                onClick={() => setStep('test')}
                disabled={!canProceedFromConfig()}
                className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Next: Test Connection
              </button>
            )}

            {step === 'test' && !testResult?.success && (
              <button
                onClick={handleTest}
                disabled={testConnection.isPending || createConnector.isPending}
                className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50"
              >
                {testConnection.isPending || createConnector.isPending ? 'Testing...' : 'Test Connection'}
              </button>
            )}

            {step === 'schedule' && (
              <button
                onClick={handleComplete}
                className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700"
              >
                Complete Setup
              </button>
            )}
          </div>
        </div>
      </motion.div>
    </motion.div>
  );
}

export default ConnectorForm;
