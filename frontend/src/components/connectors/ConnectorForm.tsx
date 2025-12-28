import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useCreateConnector, useTestConnection } from '../../api/hooks/useConnectors';
import {
  inputClasses,
  selectClasses,
  textareaClasses,
  checkboxClasses,
  helperTextClasses,
  labelClasses,
  inlineLabelClasses,
  subsectionHeaderClasses,
  dividerClasses,
} from '../../utils/formStyles';

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
  aws_region: string;
  aws_access_key: string;
  aws_secret_key: string;
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
  oauth_token_url: string;
  oauth_client_id: string;
  oauth_client_secret: string;
  oauth_scopes: string;
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
    aws_region: 'us-east-1',
    aws_access_key: '',
    aws_secret_key: '',
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
    oauth_token_url: '',
    oauth_client_id: '',
    oauth_client_secret: '',
    oauth_scopes: '',
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
          aws_region: formData.aws_region,
          aws_access_key: formData.aws_access_key || undefined,
          aws_secret_key: formData.aws_secret_key || undefined,
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
        config.oauth_token_url = formData.oauth_token_url;
        config.oauth_client_id = formData.oauth_client_id;
        config.oauth_client_secret = formData.oauth_client_secret;
        config.oauth_scopes = formData.oauth_scopes ? formData.oauth_scopes.split(',').map(s => s.trim()) : [];
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
      if (formData.auth_type === 'oauth2' && (!formData.oauth_token_url || !formData.oauth_client_id || !formData.oauth_client_secret)) return false;
      return true;
    }
    return true;
  };

  const renderDatabaseConfig = () => (
    <>
      <div className="grid grid-cols-3 gap-4">
        <div className="col-span-2">
          <label className={labelClasses}>Host *</label>
          <input
            type="text"
            value={formData.host}
            onChange={(e) => updateField('host', e.target.value)}
            placeholder="localhost"
            className={inputClasses}
          />
        </div>
        <div>
          <label className={labelClasses}>Port *</label>
          <input
            type="number"
            value={formData.port}
            onChange={(e) => updateField('port', parseInt(e.target.value))}
            className={inputClasses}
          />
        </div>
      </div>

      <div>
        <label className={labelClasses}>Database *</label>
        <input
          type="text"
          value={formData.database}
          onChange={(e) => updateField('database', e.target.value)}
          placeholder="claims_db"
          className={inputClasses}
        />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className={labelClasses}>Username *</label>
          <input
            type="text"
            value={formData.username}
            onChange={(e) => updateField('username', e.target.value)}
            placeholder="db_user"
            className={inputClasses}
          />
        </div>
        <div>
          <label className={labelClasses}>Password</label>
          <input
            type="password"
            value={formData.password}
            onChange={(e) => updateField('password', e.target.value)}
            placeholder="••••••••"
            className={inputClasses}
          />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className={labelClasses}>SSL Mode</label>
          <select
            value={formData.ssl_mode}
            onChange={(e) => updateField('ssl_mode', e.target.value)}
            className={selectClasses}
          >
            {SSL_MODES.map((mode) => (
              <option key={mode.value} value={mode.value}>
                {mode.label}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className={labelClasses}>Schema</label>
          <input
            type="text"
            value={formData.schema_name}
            onChange={(e) => updateField('schema_name', e.target.value)}
            placeholder="public"
            className={inputClasses}
          />
        </div>
      </div>

      <div>
        <label className={labelClasses}>Table (optional)</label>
        <input
          type="text"
          value={formData.table}
          onChange={(e) => updateField('table', e.target.value)}
          placeholder="claims"
          className={inputClasses}
        />
      </div>
    </>
  );

  const renderS3Config = () => (
    <>
      <div>
        <label className={labelClasses}>Bucket Name *</label>
        <input
          type="text"
          value={formData.bucket}
          onChange={(e) => updateField('bucket', e.target.value)}
          placeholder="my-claims-bucket"
          className={inputClasses}
        />
      </div>

      <div>
        <label className={labelClasses}>AWS Region</label>
        <select
          value={formData.aws_region}
          onChange={(e) => updateField('aws_region', e.target.value)}
          className={selectClasses}
        >
          {AWS_REGIONS.map((r) => (
            <option key={r.value} value={r.value}>
              {r.label}
            </option>
          ))}
        </select>
        <p className={helperTextClasses}>Leave empty for IAM role-based authentication</p>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className={labelClasses}>Access Key ID</label>
          <input
            type="text"
            value={formData.aws_access_key}
            onChange={(e) => updateField('aws_access_key', e.target.value)}
            placeholder="AKIA..."
            className={inputClasses}
          />
        </div>
        <div>
          <label className={labelClasses}>Secret Access Key</label>
          <input
            type="password"
            value={formData.aws_secret_key}
            onChange={(e) => updateField('aws_secret_key', e.target.value)}
            placeholder="••••••••"
            className={inputClasses}
          />
        </div>
      </div>

      <div>
        <label className={labelClasses}>Custom Endpoint URL</label>
        <input
          type="text"
          value={formData.endpoint_url}
          onChange={(e) => updateField('endpoint_url', e.target.value)}
          placeholder="https://minio.example.com"
          className={inputClasses}
        />
        <p className={helperTextClasses}>For S3-compatible services like MinIO</p>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className={labelClasses}>Path Prefix</label>
          <input
            type="text"
            value={formData.prefix}
            onChange={(e) => updateField('prefix', e.target.value)}
            placeholder="claims/incoming/"
            className={inputClasses}
          />
        </div>
        <div>
          <label className={labelClasses}>File Pattern</label>
          <input
            type="text"
            value={formData.path_pattern}
            onChange={(e) => updateField('path_pattern', e.target.value)}
            placeholder="*.csv"
            className={inputClasses}
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
          <label className={labelClasses}>Host *</label>
          <input
            type="text"
            value={formData.host}
            onChange={(e) => updateField('host', e.target.value)}
            placeholder="sftp.example.com"
            className={inputClasses}
          />
        </div>
        <div>
          <label className={labelClasses}>Port</label>
          <input
            type="number"
            value={formData.port}
            onChange={(e) => updateField('port', parseInt(e.target.value))}
            className={inputClasses}
          />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className={labelClasses}>Username *</label>
          <input
            type="text"
            value={formData.username}
            onChange={(e) => updateField('username', e.target.value)}
            placeholder="sftp_user"
            className={inputClasses}
          />
        </div>
        <div>
          <label className={labelClasses}>Password</label>
          <input
            type="password"
            value={formData.password}
            onChange={(e) => updateField('password', e.target.value)}
            placeholder="••••••••"
            className={inputClasses}
          />
        </div>
      </div>

      <div>
        <label className={labelClasses}>
          Private Key (PEM format)
        </label>
        <textarea
          value={formData.private_key}
          onChange={(e) => updateField('private_key', e.target.value)}
          placeholder="-----BEGIN RSA PRIVATE KEY-----&#10;...&#10;-----END RSA PRIVATE KEY-----"
          rows={4}
          className={textareaClasses}
        />
        <p className={helperTextClasses}>Use instead of password for key-based auth</p>
      </div>

      {formData.private_key && (
        <div>
          <label className={labelClasses}>Key Passphrase</label>
          <input
            type="password"
            value={formData.private_key_passphrase}
            onChange={(e) => updateField('private_key_passphrase', e.target.value)}
            placeholder="••••••••"
            className={inputClasses}
          />
        </div>
      )}

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className={labelClasses}>Remote Path</label>
          <input
            type="text"
            value={formData.remote_path}
            onChange={(e) => updateField('remote_path', e.target.value)}
            placeholder="/claims/incoming"
            className={inputClasses}
          />
        </div>
        <div>
          <label className={labelClasses}>File Pattern</label>
          <input
            type="text"
            value={formData.path_pattern}
            onChange={(e) => updateField('path_pattern', e.target.value)}
            placeholder="*.edi"
            className={inputClasses}
          />
        </div>
      </div>

      {renderFileFormatConfig()}
    </>
  );

  const renderFileFormatConfig = () => (
    <>
      <div className={dividerClasses}>
        <h4 className={subsectionHeaderClasses}>File Format Settings</h4>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className={labelClasses}>File Format</label>
            <select
              value={formData.file_format}
              onChange={(e) => updateField('file_format', e.target.value)}
              className={selectClasses}
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
              <label className={labelClasses}>Delimiter</label>
              <select
                value={formData.delimiter}
                onChange={(e) => updateField('delimiter', e.target.value)}
                className={selectClasses}
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
                className={checkboxClasses}
              />
              <span className={inlineLabelClasses}>File has header row</span>
            </label>
          </div>
        )}

        <div className="mt-3">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={formData.archive_processed}
              onChange={(e) => updateField('archive_processed', e.target.checked)}
              className={checkboxClasses}
            />
            <span className={inlineLabelClasses}>Archive files after processing</span>
          </label>
        </div>

        {formData.archive_processed && (
          <div className="mt-3">
            <label className={labelClasses}>Archive Path</label>
            <input
              type="text"
              value={formData.archive_path}
              onChange={(e) => updateField('archive_path', e.target.value)}
              placeholder={formData.subtype === 's3' ? 'archive/processed/' : '/archive/processed'}
              className={inputClasses}
            />
          </div>
        )}
      </div>
    </>
  );

  const renderAuthConfig = () => (
    <>
      <div>
        <label className={labelClasses}>Authentication</label>
        <select
          value={formData.auth_type}
          onChange={(e) => updateField('auth_type', e.target.value)}
          className={selectClasses}
        >
          {AUTH_TYPES.map((t) => (
            <option key={t.value} value={t.value}>{t.label}</option>
          ))}
        </select>
      </div>

      {formData.auth_type === 'api_key' && (
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className={labelClasses}>API Key *</label>
            <input
              type="password"
              value={formData.api_key}
              onChange={(e) => updateField('api_key', e.target.value)}
              placeholder="Your API key"
              className={inputClasses}
            />
          </div>
          <div>
            <label className={labelClasses}>Header Name</label>
            <input
              type="text"
              value={formData.api_key_header}
              onChange={(e) => updateField('api_key_header', e.target.value)}
              placeholder="X-API-Key"
              className={inputClasses}
            />
          </div>
        </div>
      )}

      {formData.auth_type === 'basic' && (
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className={labelClasses}>Username *</label>
            <input
              type="text"
              value={formData.username}
              onChange={(e) => updateField('username', e.target.value)}
              placeholder="username"
              className={inputClasses}
            />
          </div>
          <div>
            <label className={labelClasses}>Password *</label>
            <input
              type="password"
              value={formData.password}
              onChange={(e) => updateField('password', e.target.value)}
              placeholder="••••••••"
              className={inputClasses}
            />
          </div>
        </div>
      )}

      {formData.auth_type === 'bearer' && (
        <div>
          <label className={labelClasses}>Bearer Token *</label>
          <input
            type="password"
            value={formData.bearer_token}
            onChange={(e) => updateField('bearer_token', e.target.value)}
            placeholder="Your bearer token"
            className={inputClasses}
          />
        </div>
      )}

      {formData.auth_type === 'oauth2' && (
        <>
          <div>
            <label className={labelClasses}>Token URL *</label>
            <input
              type="text"
              value={formData.oauth_token_url}
              onChange={(e) => updateField('oauth_token_url', e.target.value)}
              placeholder="https://auth.example.com/oauth/token"
              className={inputClasses}
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className={labelClasses}>Client ID *</label>
              <input
                type="text"
                value={formData.oauth_client_id}
                onChange={(e) => updateField('oauth_client_id', e.target.value)}
                placeholder="client_id"
                className={inputClasses}
              />
            </div>
            <div>
              <label className={labelClasses}>Client Secret *</label>
              <input
                type="password"
                value={formData.oauth_client_secret}
                onChange={(e) => updateField('oauth_client_secret', e.target.value)}
                placeholder="••••••••"
                className={inputClasses}
              />
            </div>
          </div>
          <div>
            <label className={labelClasses}>Scopes (comma-separated)</label>
            <input
              type="text"
              value={formData.oauth_scopes}
              onChange={(e) => updateField('oauth_scopes', e.target.value)}
              placeholder="system/*.read, patient/*.read"
              className={inputClasses}
            />
          </div>
        </>
      )}
    </>
  );

  const renderRESTConfig = () => (
    <>
      <div>
        <label className={labelClasses}>Base URL *</label>
        <input
          type="text"
          value={formData.base_url}
          onChange={(e) => updateField('base_url', e.target.value)}
          placeholder="https://api.example.com"
          className={inputClasses}
        />
      </div>

      <div>
        <label className={labelClasses}>Data Endpoint</label>
        <input
          type="text"
          value={formData.api_endpoint}
          onChange={(e) => updateField('api_endpoint', e.target.value)}
          placeholder="/v1/claims"
          className={inputClasses}
        />
      </div>

      {renderAuthConfig()}

      <div className={dividerClasses}>
        <h4 className={subsectionHeaderClasses}>Response Settings</h4>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className={labelClasses}>Pagination Type</label>
            <select
              value={formData.pagination_type}
              onChange={(e) => updateField('pagination_type', e.target.value)}
              className={selectClasses}
            >
              {PAGINATION_TYPES.map((t) => (
                <option key={t.value} value={t.value}>{t.label}</option>
              ))}
            </select>
          </div>
          <div>
            <label className={labelClasses}>Data Path</label>
            <input
              type="text"
              value={formData.data_path}
              onChange={(e) => updateField('data_path', e.target.value)}
              placeholder="data.items"
              className={inputClasses}
            />
            <p className={helperTextClasses}>JSON path to records array</p>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-4 mt-3">
          <div>
            <label className={labelClasses}>Timeout (sec)</label>
            <input
              type="number"
              value={formData.timeout}
              onChange={(e) => updateField('timeout', parseInt(e.target.value))}
              min={5}
              max={300}
              className={inputClasses}
            />
          </div>
          <div>
            <label className={labelClasses}>Rate Limit</label>
            <input
              type="number"
              value={formData.rate_limit}
              onChange={(e) => updateField('rate_limit', parseInt(e.target.value))}
              min={1}
              max={100}
              className={inputClasses}
            />
            <p className={helperTextClasses}>req/sec</p>
          </div>
          <div className="flex items-end pb-2">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={formData.verify_ssl}
                onChange={(e) => updateField('verify_ssl', e.target.checked)}
                className={checkboxClasses}
              />
              <span className={inlineLabelClasses}>Verify SSL</span>
            </label>
          </div>
        </div>
      </div>
    </>
  );

  const renderFHIRConfig = () => (
    <>
      <div>
        <label className={labelClasses}>FHIR Server URL *</label>
        <input
          type="text"
          value={formData.base_url}
          onChange={(e) => updateField('base_url', e.target.value)}
          placeholder="https://fhir.example.com/r4"
          className={inputClasses}
        />
      </div>

      <div>
        <label className={labelClasses}>Resource Types</label>
        <div className="grid grid-cols-2 gap-2 mt-1">
          {FHIR_RESOURCES.map((r) => (
            <label key={r.value} className="flex items-center gap-2 cursor-pointer p-2 border border-navy-700/50 rounded-lg bg-navy-800/50 hover:bg-navy-700/50">
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
                className={checkboxClasses}
              />
              <span className={inlineLabelClasses}>{r.label}</span>
            </label>
          ))}
        </div>
      </div>

      {renderAuthConfig()}

      <div className={dividerClasses}>
        <h4 className={subsectionHeaderClasses}>Connection Settings</h4>

        <div className="grid grid-cols-3 gap-4">
          <div>
            <label className={labelClasses}>Timeout (sec)</label>
            <input
              type="number"
              value={formData.timeout}
              onChange={(e) => updateField('timeout', parseInt(e.target.value))}
              min={10}
              max={300}
              className={inputClasses}
            />
          </div>
          <div>
            <label className={labelClasses}>Rate Limit</label>
            <input
              type="number"
              value={formData.rate_limit}
              onChange={(e) => updateField('rate_limit', parseInt(e.target.value))}
              min={1}
              max={50}
              className={inputClasses}
            />
            <p className={helperTextClasses}>req/sec</p>
          </div>
          <div className="flex items-end pb-2">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={formData.verify_ssl}
                onChange={(e) => updateField('verify_ssl', e.target.checked)}
                className={checkboxClasses}
              />
              <span className={inlineLabelClasses}>Verify SSL</span>
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
        className="bg-navy-800 rounded-xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="px-6 py-4 border-b border-navy-700/50 flex items-center justify-between">
          <div>
            <h2 className="text-xl font-bold text-white">Add Data Source Connector</h2>
            <p className="text-sm text-navy-400 mt-1">
              {step === 'type' && 'Select connector type'}
              {step === 'config' && 'Configure connection settings'}
              {step === 'test' && 'Test your connection'}
              {step === 'schedule' && 'Configure sync schedule'}
            </p>
          </div>
          <button onClick={onClose} className="text-navy-400 hover:text-white">
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Progress Steps */}
        <div className="px-6 py-3 bg-navy-800/50 border-b border-navy-700/50">
          <div className="flex items-center justify-between">
            {['type', 'config', 'test', 'schedule'].map((s, i) => (
              <div key={s} className="flex items-center">
                <div
                  className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${
                    step === s
                      ? 'bg-kirk text-white'
                      : ['type', 'config', 'test', 'schedule'].indexOf(step) > i
                      ? 'bg-risk-safe text-white'
                      : 'bg-navy-700 text-navy-400'
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
                        ? 'bg-risk-safe'
                        : 'bg-navy-700'
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
                  <div key={ct.type} className="border border-navy-700/50 rounded-lg p-4">
                    <div className="flex items-center gap-3 mb-3">
                      <div className="p-2 bg-kirk/20 rounded-lg">
                        <svg className="w-5 h-5 text-kirk" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={ct.icon} />
                        </svg>
                      </div>
                      <span className="font-medium text-white">{ct.label}</span>
                    </div>
                    <div className="grid grid-cols-3 gap-2">
                      {ct.subtypes.map((st) => (
                        <button
                          key={st.value}
                          onClick={() => selectType(ct.type, st.value, st.port)}
                          className="p-3 text-left rounded-lg border border-navy-700/50 hover:border-kirk hover:bg-kirk/10 transition-colors"
                        >
                          <span className="font-medium text-navy-200 block">{st.label}</span>
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
                  <label className={labelClasses}>Connector Name *</label>
                  <input
                    type="text"
                    value={formData.name}
                    onChange={(e) => updateField('name', e.target.value)}
                    placeholder={`e.g., Production ${formData.subtype.toUpperCase()} Claims`}
                    className={inputClasses}
                  />
                </div>

                <div>
                  <label className={labelClasses}>Data Type</label>
                  <select
                    value={formData.data_type}
                    onChange={(e) => updateField('data_type', e.target.value)}
                    className={selectClasses}
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
                    <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-kirk mx-auto mb-4"></div>
                    <p className="text-navy-300">Testing connection...</p>
                  </div>
                ) : testResult ? (
                  <div>
                    <div
                      className={`w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-4 ${
                        testResult.success ? 'bg-risk-safe/20' : 'bg-risk-critical/20'
                      }`}
                    >
                      {testResult.success ? (
                        <svg className="w-8 h-8 text-risk-safe" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                        </svg>
                      ) : (
                        <svg className="w-8 h-8 text-risk-critical" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                      )}
                    </div>
                    <h3 className={`text-lg font-medium ${testResult.success ? 'text-risk-safe' : 'text-risk-critical'}`}>
                      {testResult.success ? 'Connection Successful!' : 'Connection Failed'}
                    </h3>
                    <p className="text-navy-300 mt-2">{testResult.message}</p>
                    {!testResult.success && (
                      <button
                        onClick={() => setStep('config')}
                        className="mt-4 text-kirk hover:text-kirk-light font-medium"
                      >
                        Edit Configuration
                      </button>
                    )}
                  </div>
                ) : (
                  <div>
                    <div className="w-16 h-16 rounded-full bg-kirk/20 flex items-center justify-center mx-auto mb-4">
                      <svg className="w-8 h-8 text-kirk" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                      </svg>
                    </div>
                    <h3 className="text-lg font-medium text-white">Ready to Test</h3>
                    <p className="text-navy-300 mt-2">
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
                <div className="bg-risk-safe/10 border border-risk-safe/30 rounded-lg p-4 mb-6">
                  <div className="flex items-center gap-2">
                    <svg className="w-5 h-5 text-risk-safe" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    <span className="text-risk-safe font-medium">Connection verified successfully!</span>
                  </div>
                </div>

                <div>
                  <label className={labelClasses}>Sync Mode</label>
                  <select
                    value={formData.sync_mode}
                    onChange={(e) => updateField('sync_mode', e.target.value)}
                    className={selectClasses}
                  >
                    <option value="incremental">Incremental (recommended)</option>
                    <option value="full">Full sync</option>
                  </select>
                  <p className={helperTextClasses}>
                    {formData.connector_type === 'file'
                      ? 'Incremental sync tracks processed files by modification time.'
                      : 'Incremental sync only fetches new/updated records using a watermark column.'}
                  </p>
                </div>

                <div>
                  <label className={labelClasses}>Sync Schedule (cron)</label>
                  <input
                    type="text"
                    value={formData.sync_schedule}
                    onChange={(e) => updateField('sync_schedule', e.target.value)}
                    placeholder="0 */6 * * * (every 6 hours)"
                    className={inputClasses}
                  />
                  <p className={helperTextClasses}>
                    Leave empty for manual sync only. Common: <code>0 0 * * *</code> (daily), <code>0 */6 * * *</code> (every 6h)
                  </p>
                </div>

                <div>
                  <label className={labelClasses}>Batch Size</label>
                  <input
                    type="number"
                    value={formData.batch_size}
                    onChange={(e) => updateField('batch_size', parseInt(e.target.value))}
                    min={100}
                    max={10000}
                    className={inputClasses}
                  />
                  <p className={helperTextClasses}>
                    Number of records to process per batch (100-10,000).
                  </p>
                </div>

                {formData.sync_mode === 'incremental' && formData.connector_type === 'database' && (
                  <div>
                    <label className={labelClasses}>Watermark Column</label>
                    <input
                      type="text"
                      value={formData.watermark_column}
                      onChange={(e) => updateField('watermark_column', e.target.value)}
                      placeholder="updated_at"
                      className={inputClasses}
                    />
                    <p className={helperTextClasses}>
                      Column used to track incremental updates (e.g., updated_at, modified_date).
                    </p>
                  </div>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-navy-700/50 flex items-center justify-between">
          <button
            onClick={() => {
              if (step === 'config') setStep('type');
              else if (step === 'test') setStep('config');
              else if (step === 'schedule') setStep('test');
            }}
            className={`px-4 py-2 text-navy-400 hover:text-white ${step === 'type' ? 'invisible' : ''}`}
          >
            Back
          </button>

          <div className="flex gap-2">
            <button onClick={onClose} className="px-4 py-2 text-navy-400 hover:text-white">
              Cancel
            </button>

            {step === 'config' && (
              <button
                onClick={() => setStep('test')}
                disabled={!canProceedFromConfig()}
                className="px-4 py-2 bg-gradient-to-r from-kirk to-electric text-white rounded-lg hover:from-kirk-dark hover:to-electric disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Next: Test Connection
              </button>
            )}

            {step === 'test' && !testResult?.success && (
              <button
                onClick={handleTest}
                disabled={testConnection.isPending || createConnector.isPending}
                className="px-4 py-2 bg-gradient-to-r from-kirk to-electric text-white rounded-lg hover:from-kirk-dark hover:to-electric disabled:opacity-50"
              >
                {testConnection.isPending || createConnector.isPending ? 'Testing...' : 'Test Connection'}
              </button>
            )}

            {step === 'schedule' && (
              <button
                onClick={handleComplete}
                className="px-4 py-2 bg-risk-safe text-white rounded-lg hover:bg-risk-safe/90"
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
