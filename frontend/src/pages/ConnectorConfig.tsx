import { useState, useEffect, useMemo } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { useForm, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import cronstrue from 'cronstrue';
import {
  useCreateConnector,
  useUpdateConnector,
  useConnector,
  useTestConnection,
} from '../api/hooks/useConnectors';
import { ArrowLeft, Database, Globe, Folder, Check, Loader2, AlertCircle, Clock, Zap } from 'lucide-react';

// Zod schema for connector configuration
const baseSchema = z.object({
  name: z.string().min(1, 'Connector name is required').max(100),
  connector_type: z.enum(['database', 'api', 'file']),
  subtype: z.string().min(1, 'Connector subtype is required'),
  data_type: z.enum(['claims', 'eligibility', 'providers', 'reference']),
  sync_schedule: z.string().optional(),
  sync_mode: z.enum(['incremental', 'full']),
  batch_size: z.number().min(100).max(10000),
});

const databaseConfigSchema = z.object({
  host: z.string().min(1, 'Host is required'),
  port: z.number().min(1).max(65535),
  database: z.string().min(1, 'Database name is required'),
  username: z.string().min(1, 'Username is required'),
  password: z.string().optional(),
  ssl_mode: z.enum(['disable', 'prefer', 'require', 'verify-ca', 'verify-full']).default('prefer'),
  schema_name: z.string().default('public'),
  table: z.string().optional(),
  query: z.string().optional(),
  watermark_column: z.string().optional(),
});

const s3ConfigSchema = z.object({
  bucket: z.string().min(1, 'Bucket name is required'),
  aws_region: z.string().default('us-east-1'),
  aws_access_key: z.string().optional(),
  aws_secret_key: z.string().optional(),
  endpoint_url: z.string().optional(),
  prefix: z.string().optional(),
  path_pattern: z.string().default('*'),
  file_format: z.enum(['csv', 'json', 'edi_837', 'edi_837p', 'edi_837i']).default('csv'),
  delimiter: z.string().default(','),
  has_header: z.boolean().default(true),
  archive_processed: z.boolean().default(false),
  archive_path: z.string().optional(),
});

const sftpConfigSchema = z.object({
  host: z.string().min(1, 'Host is required'),
  port: z.number().min(1).max(65535).default(22),
  username: z.string().min(1, 'Username is required'),
  password: z.string().optional(),
  private_key: z.string().optional(),
  private_key_passphrase: z.string().optional(),
  remote_path: z.string().default('/'),
  path_pattern: z.string().default('*'),
  file_format: z.enum(['csv', 'json', 'edi_837', 'edi_837p', 'edi_837i']).default('csv'),
  delimiter: z.string().default(','),
  has_header: z.boolean().default(true),
  archive_processed: z.boolean().default(false),
  archive_path: z.string().optional(),
});

const apiConfigSchema = z.object({
  base_url: z.string().url('Must be a valid URL'),
  endpoint: z.string().default('/'),
  auth_type: z.enum(['none', 'api_key', 'basic', 'bearer', 'oauth2']).default('none'),
  api_key: z.string().optional(),
  api_key_header: z.string().default('X-API-Key'),
  username: z.string().optional(),
  password: z.string().optional(),
  bearer_token: z.string().optional(),
  oauth_token_url: z.string().optional(),
  oauth_client_id: z.string().optional(),
  oauth_client_secret: z.string().optional(),
  oauth_scopes: z.string().optional(),
  pagination_type: z.enum(['none', 'offset', 'page', 'cursor', 'link_header']).default('none'),
  data_path: z.string().optional(),
  rate_limit: z.number().min(1).max(100).default(10),
  timeout: z.number().min(5).max(300).default(30),
  verify_ssl: z.boolean().default(true),
});

const fhirConfigSchema = apiConfigSchema.extend({
  resource_types: z.array(z.string()).min(1, 'Select at least one resource type'),
});

// Combined form schema - use discriminated unions based on connector_type/subtype
const formSchema = baseSchema.extend({
  connection_config: z.record(z.string(), z.unknown()),
});

type FormData = z.infer<typeof formSchema>;

type Step = 'type' | 'config' | 'test' | 'schedule';

const CONNECTOR_TYPES = [
  {
    type: 'database',
    label: 'Database',
    description: 'Connect to relational databases',
    icon: Database,
    subtypes: [
      { value: 'postgresql', label: 'PostgreSQL', port: 5432 },
      { value: 'mysql', label: 'MySQL', port: 3306 },
      { value: 'sqlserver', label: 'SQL Server', port: 1433 },
    ],
  },
  {
    type: 'api',
    label: 'API',
    description: 'Connect to REST or FHIR APIs',
    icon: Globe,
    subtypes: [
      { value: 'rest', label: 'REST API', port: 443 },
      { value: 'fhir', label: 'HL7 FHIR', port: 443 },
    ],
  },
  {
    type: 'file',
    label: 'File System',
    description: 'Connect to cloud storage or SFTP',
    icon: Folder,
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

const SCHEDULE_PRESETS = [
  { value: '', label: 'Manual only', description: 'Trigger syncs manually' },
  { value: '0 * * * *', label: 'Every hour', description: 'At minute 0' },
  { value: '0 */6 * * *', label: 'Every 6 hours', description: 'At 00:00, 06:00, 12:00, 18:00' },
  { value: '0 0 * * *', label: 'Daily', description: 'At midnight' },
  { value: '0 0 * * 0', label: 'Weekly', description: 'Sunday at midnight' },
  { value: 'custom', label: 'Custom', description: 'Enter a custom cron expression' },
];

export function ConnectorConfig() {
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const isEditMode = !!id;

  const [step, setStep] = useState<Step>(isEditMode ? 'config' : 'type');
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);
  const [createdConnectorId, setCreatedConnectorId] = useState<string | null>(id || null);
  const [showCustomCron, setShowCustomCron] = useState(false);

  // Fetch existing connector for edit mode
  const { data: existingConnector, isLoading: isLoadingConnector } = useConnector(id || '');

  const createConnector = useCreateConnector();
  const updateConnector = useUpdateConnector();
  const testConnection = useTestConnection();

  // Form setup with react-hook-form + zod
  const {
    control,
    watch,
    setValue,
    reset,
    formState: { errors },
  } = useForm<FormData>({
    resolver: zodResolver(formSchema),
    mode: 'onChange',
    defaultValues: {
      name: '',
      connector_type: 'database',
      subtype: '',
      data_type: 'claims',
      sync_schedule: '',
      sync_mode: 'incremental',
      batch_size: 1000,
      connection_config: {},
    },
  });

  const connectorType = watch('connector_type');
  const subtype = watch('subtype');
  const syncSchedule = watch('sync_schedule');
  const syncMode = watch('sync_mode');

  // Populate form with existing connector data in edit mode
  useEffect(() => {
    if (isEditMode && existingConnector) {
      reset({
        name: existingConnector.name,
        connector_type: existingConnector.connector_type as 'database' | 'api' | 'file',
        subtype: existingConnector.subtype,
        data_type: existingConnector.data_type as 'claims' | 'eligibility' | 'providers' | 'reference',
        sync_schedule: existingConnector.sync_schedule || '',
        sync_mode: (existingConnector.sync_mode as 'incremental' | 'full') || 'incremental',
        batch_size: existingConnector.batch_size || 1000,
        connection_config: existingConnector.connection_config || {},
      });

      // Check if it's a custom cron
      const isPreset = SCHEDULE_PRESETS.some(
        (p) => p.value === existingConnector.sync_schedule && p.value !== 'custom'
      );
      if (existingConnector.sync_schedule && !isPreset) {
        setShowCustomCron(true);
      }
    }
  }, [isEditMode, existingConnector, reset]);

  // Human-readable cron description
  const cronDescription = useMemo(() => {
    if (!syncSchedule) return null;
    try {
      return cronstrue.toString(syncSchedule, { verbose: true });
    } catch {
      return 'Invalid cron expression';
    }
  }, [syncSchedule]);

  const selectType = (type: string, st: string, port: number) => {
    setValue('connector_type', type as 'database' | 'api' | 'file');
    setValue('subtype', st);

    // Set default port in connection_config
    const config = watch('connection_config') || {};
    setValue('connection_config', { ...config, port });

    setStep('config');
  };

  const getValidationSchema = () => {
    if (connectorType === 'database') {
      return databaseConfigSchema;
    } else if (connectorType === 'file') {
      if (subtype === 's3' || subtype === 'azure_blob') {
        return s3ConfigSchema;
      } else if (subtype === 'sftp') {
        return sftpConfigSchema;
      }
    } else if (connectorType === 'api') {
      if (subtype === 'fhir') {
        return fhirConfigSchema;
      }
      return apiConfigSchema;
    }
    return z.object({});
  };

  const validateConfig = () => {
    const config = watch('connection_config');
    const schema = getValidationSchema();
    const result = schema.safeParse(config);
    return result.success;
  };

  const updateConfig = (key: string, value: unknown) => {
    const config = watch('connection_config') || {};
    setValue('connection_config', { ...config, [key]: value });
  };

  const getConfigValue = <T,>(key: string, defaultValue: T): T => {
    const config = watch('connection_config') || {};
    return (config[key] as T) ?? defaultValue;
  };

  const handleTest = async () => {
    const data = watch();

    if (!createdConnectorId) {
      // Create connector first to test
      try {
        const connector = await createConnector.mutateAsync({
          name: data.name || `Test ${data.subtype} connector`,
          connector_type: data.connector_type,
          subtype: data.subtype,
          data_type: data.data_type,
          connection_config: data.connection_config,
          sync_mode: data.sync_mode,
          batch_size: data.batch_size,
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
      // Update and test existing connector
      try {
        if (isEditMode) {
          await updateConnector.mutateAsync({
            connectorId: createdConnectorId,
            name: data.name,
            connection_config: data.connection_config,
            sync_mode: data.sync_mode,
            batch_size: data.batch_size,
          });
        }

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

  const handleComplete = async () => {
    const data = watch();

    try {
      if (createdConnectorId) {
        await updateConnector.mutateAsync({
          connectorId: createdConnectorId,
          sync_schedule: data.sync_schedule || undefined,
          sync_mode: data.sync_mode,
          batch_size: data.batch_size,
        });
      }
      navigate('/data-sources');
    } catch (error) {
      console.error('Failed to save connector:', error);
    }
  };

  const canProceedFromConfig = () => {
    const name = watch('name');
    if (!name) return false;
    return validateConfig();
  };

  if (isEditMode && isLoadingConnector) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="w-8 h-8 animate-spin text-indigo-600" />
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <button
          onClick={() => navigate('/data-sources')}
          className="flex items-center gap-2 text-gray-600 hover:text-gray-900 mb-4"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Data Sources
        </button>
        <h1 className="text-2xl font-bold text-gray-900">
          {isEditMode ? 'Edit Connector' : 'Add Data Source Connector'}
        </h1>
        <p className="text-gray-500 mt-1">
          {step === 'type' && 'Select the type of data source you want to connect'}
          {step === 'config' && 'Configure connection settings'}
          {step === 'test' && 'Test your connection'}
          {step === 'schedule' && 'Configure sync schedule'}
        </p>
      </div>

      {/* Progress Steps */}
      <div className="mb-8">
        <div className="flex items-center justify-between">
          {['type', 'config', 'test', 'schedule'].map((s, i) => (
            <div key={s} className="flex items-center">
              <div
                className={`w-10 h-10 rounded-full flex items-center justify-center text-sm font-medium transition-colors ${
                  step === s
                    ? 'bg-indigo-600 text-white'
                    : ['type', 'config', 'test', 'schedule'].indexOf(step) > i
                    ? 'bg-green-500 text-white'
                    : 'bg-gray-200 text-gray-600'
                }`}
              >
                {['type', 'config', 'test', 'schedule'].indexOf(step) > i ? (
                  <Check className="w-5 h-5" />
                ) : (
                  i + 1
                )}
              </div>
              {i < 3 && (
                <div
                  className={`w-24 h-1 mx-2 transition-colors ${
                    ['type', 'config', 'test', 'schedule'].indexOf(step) > i
                      ? 'bg-green-500'
                      : 'bg-gray-200'
                  }`}
                />
              )}
            </div>
          ))}
        </div>
        <div className="flex justify-between mt-2 text-sm text-gray-500">
          <span>Type</span>
          <span className="ml-8">Configure</span>
          <span className="ml-4">Test</span>
          <span>Schedule</span>
        </div>
      </div>

      {/* Content */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <AnimatePresence mode="wait">
          {/* Step 1: Select Type */}
          {step === 'type' && (
            <motion.div
              key="type"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
              className="space-y-6"
            >
              {CONNECTOR_TYPES.map((ct) => {
                const Icon = ct.icon;
                return (
                  <div key={ct.type} className="border border-gray-200 rounded-lg p-5">
                    <div className="flex items-center gap-3 mb-4">
                      <div className="p-2 bg-indigo-100 rounded-lg">
                        <Icon className="w-5 h-5 text-indigo-600" />
                      </div>
                      <div>
                        <h3 className="font-semibold text-gray-900">{ct.label}</h3>
                        <p className="text-sm text-gray-500">{ct.description}</p>
                      </div>
                    </div>
                    <div className="grid grid-cols-3 gap-3">
                      {ct.subtypes.map((st) => (
                        <button
                          key={st.value}
                          onClick={() => selectType(ct.type, st.value, st.port)}
                          className="p-4 text-left rounded-lg border border-gray-200 hover:border-indigo-500 hover:bg-indigo-50 transition-all group"
                        >
                          <span className="font-medium text-gray-800 group-hover:text-indigo-700">
                            {st.label}
                          </span>
                          <p className="text-xs text-gray-500 mt-1">Port {st.port}</p>
                        </button>
                      ))}
                    </div>
                  </div>
                );
              })}
            </motion.div>
          )}

          {/* Step 2: Configuration */}
          {step === 'config' && (
            <motion.div
              key="config"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
              className="space-y-6"
            >
              {/* Connector Name */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Connector Name *
                </label>
                <Controller
                  name="name"
                  control={control}
                  render={({ field }) => (
                    <input
                      {...field}
                      type="text"
                      placeholder={`e.g., Production ${subtype?.toUpperCase()} Claims`}
                      className={`w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent ${
                        errors.name ? 'border-red-300' : 'border-gray-300'
                      }`}
                    />
                  )}
                />
                {errors.name && (
                  <p className="text-sm text-red-600 mt-1">{errors.name.message}</p>
                )}
              </div>

              {/* Data Type */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Data Type</label>
                <Controller
                  name="data_type"
                  control={control}
                  render={({ field }) => (
                    <select
                      {...field}
                      className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
                    >
                      {DATA_TYPES.map((dt) => (
                        <option key={dt.value} value={dt.value}>
                          {dt.label} - {dt.description}
                        </option>
                      ))}
                    </select>
                  )}
                />
              </div>

              {/* Type-specific configuration */}
              {connectorType === 'database' && (
                <DatabaseConfigForm
                  getConfigValue={getConfigValue}
                  updateConfig={updateConfig}
                  subtype={subtype}
                />
              )}

              {connectorType === 'file' && subtype === 's3' && (
                <S3ConfigForm getConfigValue={getConfigValue} updateConfig={updateConfig} />
              )}

              {connectorType === 'file' && subtype === 'sftp' && (
                <SFTPConfigForm getConfigValue={getConfigValue} updateConfig={updateConfig} />
              )}

              {connectorType === 'file' && subtype === 'azure_blob' && (
                <AzureBlobConfigForm getConfigValue={getConfigValue} updateConfig={updateConfig} />
              )}

              {connectorType === 'api' && subtype === 'rest' && (
                <RESTConfigForm getConfigValue={getConfigValue} updateConfig={updateConfig} />
              )}

              {connectorType === 'api' && subtype === 'fhir' && (
                <FHIRConfigForm getConfigValue={getConfigValue} updateConfig={updateConfig} />
              )}
            </motion.div>
          )}

          {/* Step 3: Test Connection */}
          {step === 'test' && (
            <motion.div
              key="test"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
              className="text-center py-12"
            >
              {testConnection.isPending || createConnector.isPending ? (
                <div>
                  <Loader2 className="w-12 h-12 animate-spin text-indigo-600 mx-auto mb-4" />
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
                      <Check className="w-8 h-8 text-green-600" />
                    ) : (
                      <AlertCircle className="w-8 h-8 text-red-600" />
                    )}
                  </div>
                  <h3
                    className={`text-lg font-medium ${
                      testResult.success ? 'text-green-700' : 'text-red-700'
                    }`}
                  >
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
                    <Zap className="w-8 h-8 text-indigo-600" />
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
              className="space-y-6"
            >
              <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                <div className="flex items-center gap-2">
                  <Check className="w-5 h-5 text-green-600" />
                  <span className="text-green-800 font-medium">
                    Connection verified successfully!
                  </span>
                </div>
              </div>

              {/* Sync Mode */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Sync Mode</label>
                <Controller
                  name="sync_mode"
                  control={control}
                  render={({ field }) => (
                    <select
                      {...field}
                      className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
                    >
                      <option value="incremental">Incremental (recommended)</option>
                      <option value="full">Full sync</option>
                    </select>
                  )}
                />
                <p className="text-sm text-gray-500 mt-1">
                  {connectorType === 'file'
                    ? 'Incremental sync tracks processed files by modification time.'
                    : 'Incremental sync only fetches new/updated records using a watermark column.'}
                </p>
              </div>

              {/* Sync Schedule with Presets */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  <Clock className="w-4 h-4 inline mr-1" />
                  Sync Schedule
                </label>
                <div className="grid grid-cols-2 gap-3 mb-3">
                  {SCHEDULE_PRESETS.map((preset) => (
                    <button
                      key={preset.value}
                      type="button"
                      onClick={() => {
                        if (preset.value === 'custom') {
                          setShowCustomCron(true);
                        } else {
                          setValue('sync_schedule', preset.value);
                          setShowCustomCron(false);
                        }
                      }}
                      className={`p-3 text-left rounded-lg border transition-all ${
                        (syncSchedule === preset.value && !showCustomCron) ||
                        (preset.value === 'custom' && showCustomCron)
                          ? 'border-indigo-500 bg-indigo-50'
                          : 'border-gray-200 hover:border-gray-300'
                      }`}
                    >
                      <span className="font-medium text-gray-800">{preset.label}</span>
                      <p className="text-xs text-gray-500 mt-0.5">{preset.description}</p>
                    </button>
                  ))}
                </div>

                {showCustomCron && (
                  <div className="mt-3">
                    <Controller
                      name="sync_schedule"
                      control={control}
                      render={({ field }) => (
                        <input
                          {...field}
                          type="text"
                          placeholder="0 */6 * * *"
                          className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
                        />
                      )}
                    />
                  </div>
                )}

                {/* Human-readable cron description */}
                {syncSchedule && cronDescription && (
                  <div
                    className={`mt-2 p-3 rounded-lg ${
                      cronDescription === 'Invalid cron expression'
                        ? 'bg-red-50 text-red-700'
                        : 'bg-blue-50 text-blue-700'
                    }`}
                  >
                    <p className="text-sm">
                      <span className="font-medium">Schedule: </span>
                      {cronDescription}
                    </p>
                  </div>
                )}
              </div>

              {/* Batch Size */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Batch Size</label>
                <Controller
                  name="batch_size"
                  control={control}
                  render={({ field }) => (
                    <input
                      {...field}
                      type="number"
                      min={100}
                      max={10000}
                      onChange={(e) => field.onChange(parseInt(e.target.value))}
                      className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
                    />
                  )}
                />
                <p className="text-sm text-gray-500 mt-1">
                  Number of records to process per batch (100-10,000).
                </p>
              </div>

              {/* Watermark Column for incremental database sync */}
              {syncMode === 'incremental' && connectorType === 'database' && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Watermark Column
                  </label>
                  <input
                    type="text"
                    value={getConfigValue('watermark_column', '')}
                    onChange={(e) => updateConfig('watermark_column', e.target.value)}
                    placeholder="updated_at"
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
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

      {/* Footer Actions */}
      <div className="mt-6 flex items-center justify-between">
        <button
          onClick={() => {
            if (step === 'config') setStep('type');
            else if (step === 'test') setStep('config');
            else if (step === 'schedule') setStep('test');
          }}
          className={`px-4 py-2 text-gray-600 hover:text-gray-800 ${
            step === 'type' || (isEditMode && step === 'config') ? 'invisible' : ''
          }`}
        >
          Back
        </button>

        <div className="flex gap-3">
          <button
            onClick={() => navigate('/data-sources')}
            className="px-4 py-2 text-gray-600 hover:text-gray-800"
          >
            Cancel
          </button>

          {step === 'config' && (
            <button
              onClick={() => setStep('test')}
              disabled={!canProceedFromConfig()}
              className="px-6 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Next: Test Connection
            </button>
          )}

          {step === 'test' && !testResult?.success && (
            <button
              onClick={handleTest}
              disabled={testConnection.isPending || createConnector.isPending}
              className="px-6 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50"
            >
              {testConnection.isPending || createConnector.isPending
                ? 'Testing...'
                : 'Test Connection'}
            </button>
          )}

          {step === 'schedule' && (
            <button
              onClick={handleComplete}
              disabled={updateConnector.isPending}
              className="px-6 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50"
            >
              {updateConnector.isPending ? 'Saving...' : 'Complete Setup'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

// Sub-components for type-specific configuration

interface ConfigFormProps {
  getConfigValue: <T>(key: string, defaultValue: T) => T;
  updateConfig: (key: string, value: unknown) => void;
  subtype?: string;
}

function DatabaseConfigForm({ getConfigValue, updateConfig, subtype }: ConfigFormProps) {
  const defaultPort = subtype === 'postgresql' ? 5432 : subtype === 'mysql' ? 3306 : 1433;

  return (
    <div className="space-y-4 border-t border-gray-200 pt-4">
      <h4 className="font-medium text-gray-900">Database Connection</h4>

      <div className="grid grid-cols-3 gap-4">
        <div className="col-span-2">
          <label className="block text-sm font-medium text-gray-700 mb-1">Host *</label>
          <input
            type="text"
            value={getConfigValue('host', 'localhost')}
            onChange={(e) => updateConfig('host', e.target.value)}
            placeholder="localhost"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Port *</label>
          <input
            type="number"
            value={getConfigValue('port', defaultPort)}
            onChange={(e) => updateConfig('port', parseInt(e.target.value))}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
          />
        </div>
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Database *</label>
        <input
          type="text"
          value={getConfigValue('database', '')}
          onChange={(e) => updateConfig('database', e.target.value)}
          placeholder="claims_db"
          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
        />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Username *</label>
          <input
            type="text"
            value={getConfigValue('username', '')}
            onChange={(e) => updateConfig('username', e.target.value)}
            placeholder="db_user"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Password</label>
          <input
            type="password"
            value={getConfigValue('password', '')}
            onChange={(e) => updateConfig('password', e.target.value)}
            placeholder="********"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
          />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">SSL Mode</label>
          <select
            value={getConfigValue('ssl_mode', 'prefer')}
            onChange={(e) => updateConfig('ssl_mode', e.target.value)}
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
            value={getConfigValue('schema_name', 'public')}
            onChange={(e) => updateConfig('schema_name', e.target.value)}
            placeholder="public"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
          />
        </div>
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Table (optional)</label>
        <input
          type="text"
          value={getConfigValue('table', '')}
          onChange={(e) => updateConfig('table', e.target.value)}
          placeholder="claims"
          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
        />
      </div>
    </div>
  );
}

function S3ConfigForm({ getConfigValue, updateConfig }: ConfigFormProps) {
  return (
    <div className="space-y-4 border-t border-gray-200 pt-4">
      <h4 className="font-medium text-gray-900">S3 Configuration</h4>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Bucket Name *</label>
        <input
          type="text"
          value={getConfigValue('bucket', '')}
          onChange={(e) => updateConfig('bucket', e.target.value)}
          placeholder="my-claims-bucket"
          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">AWS Region</label>
        <select
          value={getConfigValue('aws_region', 'us-east-1')}
          onChange={(e) => updateConfig('aws_region', e.target.value)}
          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
        >
          {AWS_REGIONS.map((r) => (
            <option key={r.value} value={r.value}>
              {r.label}
            </option>
          ))}
        </select>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Access Key ID</label>
          <input
            type="text"
            value={getConfigValue('aws_access_key', '')}
            onChange={(e) => updateConfig('aws_access_key', e.target.value)}
            placeholder="AKIA..."
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Secret Access Key</label>
          <input
            type="password"
            value={getConfigValue('aws_secret_key', '')}
            onChange={(e) => updateConfig('aws_secret_key', e.target.value)}
            placeholder="********"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
          />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Path Prefix</label>
          <input
            type="text"
            value={getConfigValue('prefix', '')}
            onChange={(e) => updateConfig('prefix', e.target.value)}
            placeholder="claims/incoming/"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">File Pattern</label>
          <input
            type="text"
            value={getConfigValue('path_pattern', '*')}
            onChange={(e) => updateConfig('path_pattern', e.target.value)}
            placeholder="*.csv"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
          />
        </div>
      </div>

      <FileFormatConfig getConfigValue={getConfigValue} updateConfig={updateConfig} />
    </div>
  );
}

function SFTPConfigForm({ getConfigValue, updateConfig }: ConfigFormProps) {
  return (
    <div className="space-y-4 border-t border-gray-200 pt-4">
      <h4 className="font-medium text-gray-900">SFTP Configuration</h4>

      <div className="grid grid-cols-3 gap-4">
        <div className="col-span-2">
          <label className="block text-sm font-medium text-gray-700 mb-1">Host *</label>
          <input
            type="text"
            value={getConfigValue('host', '')}
            onChange={(e) => updateConfig('host', e.target.value)}
            placeholder="sftp.example.com"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Port</label>
          <input
            type="number"
            value={getConfigValue('port', 22)}
            onChange={(e) => updateConfig('port', parseInt(e.target.value))}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
          />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Username *</label>
          <input
            type="text"
            value={getConfigValue('username', '')}
            onChange={(e) => updateConfig('username', e.target.value)}
            placeholder="sftp_user"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Password</label>
          <input
            type="password"
            value={getConfigValue('password', '')}
            onChange={(e) => updateConfig('password', e.target.value)}
            placeholder="********"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
          />
        </div>
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Private Key (PEM format)
        </label>
        <textarea
          value={getConfigValue('private_key', '')}
          onChange={(e) => updateConfig('private_key', e.target.value)}
          placeholder="-----BEGIN RSA PRIVATE KEY-----"
          rows={3}
          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 font-mono text-sm"
        />
        <p className="text-xs text-gray-500 mt-1">Use instead of password for key-based auth</p>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Remote Path</label>
          <input
            type="text"
            value={getConfigValue('remote_path', '/')}
            onChange={(e) => updateConfig('remote_path', e.target.value)}
            placeholder="/claims/incoming"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">File Pattern</label>
          <input
            type="text"
            value={getConfigValue('path_pattern', '*')}
            onChange={(e) => updateConfig('path_pattern', e.target.value)}
            placeholder="*.edi"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
          />
        </div>
      </div>

      <FileFormatConfig getConfigValue={getConfigValue} updateConfig={updateConfig} />
    </div>
  );
}

function AzureBlobConfigForm({ getConfigValue, updateConfig }: ConfigFormProps) {
  return (
    <div className="space-y-4 border-t border-gray-200 pt-4">
      <h4 className="font-medium text-gray-900">Azure Blob Configuration</h4>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Storage Account Name *
        </label>
        <input
          type="text"
          value={getConfigValue('account_name', '')}
          onChange={(e) => updateConfig('account_name', e.target.value)}
          placeholder="mystorageaccount"
          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Container Name *</label>
        <input
          type="text"
          value={getConfigValue('container_name', '')}
          onChange={(e) => updateConfig('container_name', e.target.value)}
          placeholder="claims-data"
          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Connection String (optional)
        </label>
        <input
          type="password"
          value={getConfigValue('connection_string', '')}
          onChange={(e) => updateConfig('connection_string', e.target.value)}
          placeholder="DefaultEndpointsProtocol=https;AccountName=..."
          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
        />
        <p className="text-xs text-gray-500 mt-1">Leave empty to use Managed Identity</p>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Blob Prefix</label>
          <input
            type="text"
            value={getConfigValue('prefix', '')}
            onChange={(e) => updateConfig('prefix', e.target.value)}
            placeholder="claims/incoming/"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">File Pattern</label>
          <input
            type="text"
            value={getConfigValue('path_pattern', '*')}
            onChange={(e) => updateConfig('path_pattern', e.target.value)}
            placeholder="*.csv"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
          />
        </div>
      </div>

      <FileFormatConfig getConfigValue={getConfigValue} updateConfig={updateConfig} />
    </div>
  );
}

function FileFormatConfig({ getConfigValue, updateConfig }: ConfigFormProps) {
  const fileFormat = getConfigValue('file_format', 'csv');

  return (
    <div className="border-t border-gray-200 pt-4 mt-4">
      <h4 className="text-sm font-medium text-gray-900 mb-3">File Format Settings</h4>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">File Format</label>
          <select
            value={fileFormat}
            onChange={(e) => updateConfig('file_format', e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
          >
            {FILE_FORMATS.map((f) => (
              <option key={f.value} value={f.value}>
                {f.label}
              </option>
            ))}
          </select>
        </div>

        {fileFormat === 'csv' && (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Delimiter</label>
            <select
              value={getConfigValue('delimiter', ',')}
              onChange={(e) => updateConfig('delimiter', e.target.value)}
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

      {fileFormat === 'csv' && (
        <div className="mt-3">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={getConfigValue('has_header', true)}
              onChange={(e) => updateConfig('has_header', e.target.checked)}
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
            checked={getConfigValue('archive_processed', false)}
            onChange={(e) => updateConfig('archive_processed', e.target.checked)}
            className="w-4 h-4 text-indigo-600 border-gray-300 rounded focus:ring-indigo-500"
          />
          <span className="text-sm text-gray-700">Archive files after processing</span>
        </label>
      </div>

      {getConfigValue('archive_processed', false) && (
        <div className="mt-3">
          <label className="block text-sm font-medium text-gray-700 mb-1">Archive Path</label>
          <input
            type="text"
            value={getConfigValue('archive_path', '')}
            onChange={(e) => updateConfig('archive_path', e.target.value)}
            placeholder="archive/processed/"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
          />
        </div>
      )}
    </div>
  );
}

function RESTConfigForm({ getConfigValue, updateConfig }: ConfigFormProps) {
  return (
    <div className="space-y-4 border-t border-gray-200 pt-4">
      <h4 className="font-medium text-gray-900">REST API Configuration</h4>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Base URL *</label>
        <input
          type="text"
          value={getConfigValue('base_url', '')}
          onChange={(e) => updateConfig('base_url', e.target.value)}
          placeholder="https://api.example.com"
          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Data Endpoint</label>
        <input
          type="text"
          value={getConfigValue('endpoint', '/')}
          onChange={(e) => updateConfig('endpoint', e.target.value)}
          placeholder="/v1/claims"
          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
        />
      </div>

      <AuthConfig getConfigValue={getConfigValue} updateConfig={updateConfig} />

      <div className="border-t border-gray-200 pt-4 mt-4">
        <h4 className="text-sm font-medium text-gray-900 mb-3">Response Settings</h4>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Pagination Type</label>
            <select
              value={getConfigValue('pagination_type', 'none')}
              onChange={(e) => updateConfig('pagination_type', e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
            >
              {PAGINATION_TYPES.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Data Path</label>
            <input
              type="text"
              value={getConfigValue('data_path', '')}
              onChange={(e) => updateConfig('data_path', e.target.value)}
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
              value={getConfigValue('timeout', 30)}
              onChange={(e) => updateConfig('timeout', parseInt(e.target.value))}
              min={5}
              max={300}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Rate Limit</label>
            <input
              type="number"
              value={getConfigValue('rate_limit', 10)}
              onChange={(e) => updateConfig('rate_limit', parseInt(e.target.value))}
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
                checked={getConfigValue('verify_ssl', true)}
                onChange={(e) => updateConfig('verify_ssl', e.target.checked)}
                className="w-4 h-4 text-indigo-600 border-gray-300 rounded focus:ring-indigo-500"
              />
              <span className="text-sm text-gray-700">Verify SSL</span>
            </label>
          </div>
        </div>
      </div>
    </div>
  );
}

function FHIRConfigForm({ getConfigValue, updateConfig }: ConfigFormProps) {
  const resourceTypes = getConfigValue<string[]>('resource_types', ['Claim']);

  return (
    <div className="space-y-4 border-t border-gray-200 pt-4">
      <h4 className="font-medium text-gray-900">FHIR Server Configuration</h4>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">FHIR Server URL *</label>
        <input
          type="text"
          value={getConfigValue('base_url', '')}
          onChange={(e) => updateConfig('base_url', e.target.value)}
          placeholder="https://fhir.example.com/r4"
          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">Resource Types</label>
        <div className="grid grid-cols-2 gap-2">
          {FHIR_RESOURCES.map((r) => (
            <label
              key={r.value}
              className="flex items-center gap-2 cursor-pointer p-2 border border-gray-200 rounded-lg hover:bg-gray-50"
            >
              <input
                type="checkbox"
                checked={resourceTypes.includes(r.value)}
                onChange={(e) => {
                  if (e.target.checked) {
                    updateConfig('resource_types', [...resourceTypes, r.value]);
                  } else {
                    updateConfig(
                      'resource_types',
                      resourceTypes.filter((v) => v !== r.value)
                    );
                  }
                }}
                className="w-4 h-4 text-indigo-600 border-gray-300 rounded focus:ring-indigo-500"
              />
              <span className="text-sm text-gray-700">{r.label}</span>
            </label>
          ))}
        </div>
      </div>

      <AuthConfig getConfigValue={getConfigValue} updateConfig={updateConfig} />

      <div className="border-t border-gray-200 pt-4 mt-4">
        <h4 className="text-sm font-medium text-gray-900 mb-3">Connection Settings</h4>

        <div className="grid grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Timeout (sec)</label>
            <input
              type="number"
              value={getConfigValue('timeout', 30)}
              onChange={(e) => updateConfig('timeout', parseInt(e.target.value))}
              min={10}
              max={300}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Rate Limit</label>
            <input
              type="number"
              value={getConfigValue('rate_limit', 10)}
              onChange={(e) => updateConfig('rate_limit', parseInt(e.target.value))}
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
                checked={getConfigValue('verify_ssl', true)}
                onChange={(e) => updateConfig('verify_ssl', e.target.checked)}
                className="w-4 h-4 text-indigo-600 border-gray-300 rounded focus:ring-indigo-500"
              />
              <span className="text-sm text-gray-700">Verify SSL</span>
            </label>
          </div>
        </div>
      </div>
    </div>
  );
}

type AuthType = 'none' | 'api_key' | 'basic' | 'bearer' | 'oauth2';

function AuthConfig({ getConfigValue, updateConfig }: ConfigFormProps) {
  const authType = getConfigValue<AuthType>('auth_type', 'none');

  return (
    <div className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Authentication</label>
        <select
          value={authType}
          onChange={(e) => updateConfig('auth_type', e.target.value)}
          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
        >
          {AUTH_TYPES.map((t) => (
            <option key={t.value} value={t.value}>
              {t.label}
            </option>
          ))}
        </select>
      </div>

      {authType === 'api_key' && (
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">API Key *</label>
            <input
              type="password"
              value={getConfigValue('api_key', '')}
              onChange={(e) => updateConfig('api_key', e.target.value)}
              placeholder="Your API key"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Header Name</label>
            <input
              type="text"
              value={getConfigValue('api_key_header', 'X-API-Key')}
              onChange={(e) => updateConfig('api_key_header', e.target.value)}
              placeholder="X-API-Key"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
            />
          </div>
        </div>
      )}

      {authType === 'basic' && (
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Username *</label>
            <input
              type="text"
              value={getConfigValue('username', '')}
              onChange={(e) => updateConfig('username', e.target.value)}
              placeholder="username"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Password *</label>
            <input
              type="password"
              value={getConfigValue('password', '')}
              onChange={(e) => updateConfig('password', e.target.value)}
              placeholder="********"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
            />
          </div>
        </div>
      )}

      {authType === 'bearer' && (
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Bearer Token *</label>
          <input
            type="password"
            value={getConfigValue('bearer_token', '')}
            onChange={(e) => updateConfig('bearer_token', e.target.value)}
            placeholder="Your bearer token"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
          />
        </div>
      )}

      {authType === 'oauth2' && (
        <>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Token URL *</label>
            <input
              type="text"
              value={getConfigValue('oauth_token_url', '')}
              onChange={(e) => updateConfig('oauth_token_url', e.target.value)}
              placeholder="https://auth.example.com/oauth/token"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Client ID *</label>
              <input
                type="text"
                value={getConfigValue('oauth_client_id', '')}
                onChange={(e) => updateConfig('oauth_client_id', e.target.value)}
                placeholder="client_id"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Client Secret *
              </label>
              <input
                type="password"
                value={getConfigValue('oauth_client_secret', '')}
                onChange={(e) => updateConfig('oauth_client_secret', e.target.value)}
                placeholder="********"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
              />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Scope</label>
            <input
              type="text"
              value={getConfigValue('oauth_scopes', '')}
              onChange={(e) => updateConfig('oauth_scopes', e.target.value)}
              placeholder="system/*.read"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
            />
          </div>
        </>
      )}
    </div>
  );
}

export default ConnectorConfig;
