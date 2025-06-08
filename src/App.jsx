import React, { useState, useCallback } from "react";
import { useDropzone } from "react-dropzone";
import axios from "axios";
import { 
  FolderOpen, 
  FileText, 
  Download, 
  AlertCircle, 
  CheckCircle, 
  Clock,
  Eye,
  X
} from "lucide-react";

const API_BASE_URL = "http://localhost:8000";

export default function App() {
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [selectedFile, setSelectedFile] = useState(null);

  const onDrop = useCallback(async (acceptedFiles) => {
    setLoading(true);
    setError(null);
    
    const formData = new FormData();
    acceptedFiles.forEach((file) => {
      formData.append("files", file);
    });

    try {
      const res = await axios.post(`${API_BASE_URL}/classify`, formData, {
        headers: { "Content-Type": "multipart/form-data" },
        timeout: 30000, // 30 second timeout
      });

      const newFiles = Object.entries(res.data).map(([name, data]) => ({
        id: Date.now() + Math.random(), // Unique ID
        originalName: name,
        renamed: data.renamed,
        category: data.category,
        subcategory: data.subcategory,
        preview: data.text,
        metadata: data.metadata || {},
        idValidation: data.id_validation,
        dateValidation: data.date_validation,
        hasError: data.error ? true : false,
        error: data.error
      }));

      setFiles((prev) => [...prev, ...newFiles]);
    } catch (err) {
      console.error("Error during classification:", err);
      if (err.code === 'ECONNABORTED') {
        setError("Request timeout - please try with smaller files or fewer files at once");
      } else if (err.response?.status === 422) {
        setError("Invalid file format - please upload PDF, PNG, JPG, or JPEG files");
      } else if (err.response?.status >= 500) {
        setError("Server error - please check if the backend is running");
      } else {
        setError(`Classification failed: ${err.message}`);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    multiple: true,
    accept: {
      'application/pdf': ['.pdf'],
      'image/*': ['.png', '.jpg', '.jpeg', '.tiff', '.bmp']
    },
    maxSize: 10 * 1024 * 1024 // 10MB limit per file
  });

  const clearFiles = () => {
    setFiles([]);
    setError(null);
  };

  const removeFile = (fileId) => {
    setFiles(prev => prev.filter(f => f.id !== fileId));
  };

  const downloadResults = () => {
    const results = files.map(file => ({
      original_name: file.originalName,
      renamed: file.renamed,
      category: file.category,
      subcategory: file.subcategory,
      metadata: file.metadata,
      validation: {
        id_validation: file.idValidation,
        date_validation: file.dateValidation
      }
    }));

    const dataStr = JSON.stringify(results, null, 2);
    const dataBlob = new Blob([dataStr], { type: 'application/json' });
    const url = URL.createObjectURL(dataBlob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `mortgage_classification_results_${new Date().toISOString().split('T')[0]}.json`;
    link.click();
    URL.revokeObjectURL(url);
  };

  // Group files by category
  const grouped = files.reduce((acc, file) => {
    if (!acc[file.category]) acc[file.category] = [];
    acc[file.category].push(file);
    return acc;
  }, {});

  const getValidationIcon = (file) => {
    if (file.hasError) return <AlertCircle className="w-4 h-4 text-red-500" />;
    if (file.idValidation?.is_valid || file.dateValidation?.is_valid) {
      return <CheckCircle className="w-4 h-4 text-green-500" />;
    }
    if (file.idValidation?.is_valid === false || file.dateValidation?.is_valid === false) {
      return <AlertCircle className="w-4 h-4 text-yellow-500" />;
    }
    return <Clock className="w-4 h-4 text-gray-400" />;
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 py-6">
          <h1 className="text-3xl font-bold text-gray-900">
            📂 Mortgage Document Automation System
          </h1>
          <p className="text-gray-600 mt-2">
            Upload mortgage documents for automatic classification, validation, and organization
          </p>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 py-8 space-y-8">
        {/* Upload Area */}
        <div className="bg-white rounded-xl shadow-sm p-6">
          <div
            {...getRootProps()}
            className={`border-2 border-dashed p-8 rounded-xl text-center cursor-pointer transition-all
              ${isDragActive 
                ? 'border-blue-400 bg-blue-50' 
                : 'border-gray-300 hover:border-blue-400 hover:bg-gray-50'
              }`}
          >
            <input {...getInputProps()} />
            <FolderOpen className="w-16 h-16 text-gray-400 mx-auto mb-4" />
            
            {loading ? (
              <div className="space-y-2">
                <div className="animate-spin w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full mx-auto"></div>
                <p className="text-gray-600">Processing documents...</p>
              </div>
            ) : (
              <div className="space-y-2">
                <p className="text-xl font-semibold text-gray-700">
                  {isDragActive ? "Drop files here" : "Drag & drop files or click to browse"}
                </p>
                <p className="text-gray-500">
                  Supports PDF, PNG, JPG, JPEG (Max 10MB per file)
                </p>
              </div>
            )}
          </div>

          {/* Error Display */}
          {error && (
            <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-lg flex items-center space-x-2">
              <AlertCircle className="w-5 h-5 text-red-500" />
              <span className="text-red-700">{error}</span>
              <button
                onClick={() => setError(null)}
                className="ml-auto text-red-500 hover:text-red-700"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          )}
        </div>

        {/* Action Buttons */}
        {files.length > 0 && (
          <div className="flex space-x-4">
            <button
              onClick={downloadResults}
              className="flex items-center space-x-2 bg-blue-600 text-white px-6 py-3 rounded-lg hover:bg-blue-700 transition-colors"
            >
              <Download className="w-5 h-5" />
              <span>Download Results</span>
            </button>
            <button
              onClick={clearFiles}
              className="flex items-center space-x-2 bg-gray-600 text-white px-6 py-3 rounded-lg hover:bg-gray-700 transition-colors"
            >
              <X className="w-5 h-5" />
              <span>Clear All</span>
            </button>
          </div>
        )}

        {/* Results Display */}
        {Object.keys(grouped).length > 0 && (
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <h2 className="text-2xl font-bold text-gray-900">Classification Results</h2>
              <div className="text-sm text-gray-600">
                {files.length} document{files.length !== 1 ? 's' : ''} processed
              </div>
            </div>

            {Object.entries(grouped).map(([category, categoryFiles]) => (
              <div key={category} className="bg-white rounded-xl shadow-sm overflow-hidden">
                <div className={`px-6 py-4 font-semibold text-white ${getCategoryColor(category)}`}>
                  📁 {category} ({categoryFiles.length})
                </div>
                
                <div className="divide-y divide-gray-200">
                  {categoryFiles.map((file) => (
                    <div key={file.id} className="p-6 hover:bg-gray-50 transition-colors">
                      <div className="flex items-start justify-between">
                        <div className="flex-1 space-y-2">
                          <div className="flex items-center space-x-3">
                            {getValidationIcon(file)}
                            <div>
                              <h3 className="font-medium text-gray-900">{file.renamed}</h3>
                              <p className="text-sm text-gray-600">
                                Original: {file.originalName}
                              </p>
                            </div>
                          </div>

                          <div className="flex flex-wrap gap-2">
                            <span className="px-3 py-1 bg-blue-100 text-blue-800 text-xs rounded-full">
                              {file.subcategory}
                            </span>
                            {file.metadata?.client_name && (
                              <span className="px-3 py-1 bg-green-100 text-green-800 text-xs rounded-full">
                                👤 {file.metadata.client_name}
                              </span>
                            )}
                            {file.metadata?.date && (
                              <span className="px-3 py-1 bg-purple-100 text-purple-800 text-xs rounded-full">
                                📅 {file.metadata.date}
                              </span>
                            )}
                            {file.metadata?.extracted_amount && (
                              <span className="px-3 py-1 bg-yellow-100 text-yellow-800 text-xs rounded-full">
                                💰 {file.metadata.extracted_amount}
                              </span>
                            )}
                          </div>

                          {/* Validation Messages */}
                          {file.idValidation && (
                            <div className={`p-3 rounded-lg text-sm ${
                              file.idValidation.is_valid 
                                ? 'bg-green-50 text-green-800' 
                                : 'bg-yellow-50 text-yellow-800'
                            }`}>
                              <strong>ID Validation:</strong> {
                                file.idValidation.is_valid 
                                  ? `✓ Valid ${file.idValidation.id_type} (${(file.idValidation.confidence * 100).toFixed(0)}% confidence)`
                                  : `⚠️ ID validation failed - ${file.idValidation.id_type}`
                              }
                            </div>
                          )}

                          {file.dateValidation && (
                            <div className={`p-3 rounded-lg text-sm ${
                              file.dateValidation.is_valid 
                                ? 'bg-green-50 text-green-800' 
                                : 'bg-red-50 text-red-800'
                            }`}>
                              <strong>Date Validation:</strong> {
                                file.dateValidation.is_valid 
                                  ? `✓ Document is current (${file.dateValidation.days_old} days old)`
                                  : `❌ Document too old (${file.dateValidation.days_old} days, max ${file.dateValidation.max_allowed_days})`
                              }
                            </div>
                          )}

                          {file.hasError && (
                            <div className="p-3 bg-red-50 text-red-800 rounded-lg text-sm">
                              <strong>Processing Error:</strong> {file.error}
                            </div>
                          )}
                        </div>

                        <div className="ml-4 flex items-center space-x-2">
                          <button
                            onClick={() => setSelectedFile(file)}
                            className="p-2 text-gray-400 hover:text-gray-600 transition-colors"
                            title="Preview document text"
                          >
                            <Eye className="w-5 h-5" />
                          </button>
                          <button
                            onClick={() => removeFile(file.id)}
                            className="p-2 text-gray-400 hover:text-red-600 transition-colors"
                            title="Remove from results"
                          >
                            <X className="w-5 h-5" />
                          </button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Document Preview Modal */}
        {selectedFile && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
            <div className="bg-white rounded-xl max-w-4xl w-full max-h-[80vh] overflow-hidden">
              <div className="flex items-center justify-between p-6 border-b">
                <h3 className="text-lg font-semibold">Document Preview</h3>
                <button
                  onClick={() => setSelectedFile(null)}
                  className="text-gray-400 hover:text-gray-600"
                >
                  <X className="w-6 h-6" />
                </button>
              </div>
              <div className="p-6 max-h-96 overflow-y-auto">
                <div className="mb-4">
                  <h4 className="font-medium text-gray-900">{selectedFile.renamed}</h4>
                  <p className="text-sm text-gray-600">
                    {selectedFile.category} • {selectedFile.subcategory}
                  </p>
                </div>
                <div className="bg-gray-50 p-4 rounded-lg">
                  <pre className="whitespace-pre-wrap text-sm text-gray-700 font-mono">
                    {selectedFile.preview}
                  </pre>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Empty State */}
        {files.length === 0 && !loading && (
          <div className="text-center py-12">
            <FileText className="w-24 h-24 text-gray-300 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">No documents processed yet</h3>
            <p className="text-gray-600">Upload mortgage documents to get started with classification</p>
          </div>
        )}
      </div>
    </div>
  );
}

// Helper function to get category colors
function getCategoryColor(category) {
  const colors = {
    'Income': 'bg-green-600',
    'Down Payment': 'bg-blue-600', 
    'ID': 'bg-purple-600',
    'Other': 'bg-gray-600',
    'Error': 'bg-red-600'
  };
  return colors[category] || 'bg-gray-600';
}
