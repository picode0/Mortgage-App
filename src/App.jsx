import React, { useState } from "react";
import { useDropzone } from "react-dropzone";
import axios from "axios";
import { FolderOpen } from "lucide-react";

export default function App() {
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(false);

  const onDrop = async (acceptedFiles) => {
    setLoading(true);
    const formData = new FormData();
    acceptedFiles.forEach((file) => {
      formData.append("files", file);
    });

    try {
      const res = await axios.post("http://localhost:8000/classify", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });

      const newFiles = Object.entries(res.data).map(([name, data]) => ({
        originalName: name,
        renamed: data.renamed,
        category: data.category,
        subcategory: data.subcategory,
        preview: data.text,
      }));

      setFiles((prev) => [...prev, ...newFiles]);
    } catch (err) {
      console.error("Error during classification:", err);
    } finally {
      setLoading(false);
    }
  };

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    multiple: true,
  });

  // Group by category for display
  const grouped = files.reduce((acc, file) => {
    if (!acc[file.category]) acc[file.category] = [];
    acc[file.category].push(file);
    return acc;
  }, {});

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <h1 className="text-3xl font-bold mb-6">📂 Mortgage Document Classifier</h1>

      <div
        {...getRootProps()}
        className="border-4 border-dashed border-gray-300 p-8 rounded-xl text-center cursor-pointer bg-white hover:border-blue-400"
      >
        <input {...getInputProps()} />
        <div className="flex flex-col items-center justify-center gap-2">
          <FolderOpen size={40} className="text-gray-400" />
          <p className="text-gray-600">
            {isDragActive
              ? "Drop the files here ..."
              : "Drag & drop or click to select files"}
          </p>
        </div>
      </div>

      {loading && <p className="text-blue-600 mt-4">🔄 Classifying files...</p>}

      <div className="mt-10 space-y-6">
        {Object.entries(grouped).map(([category, files]) => (
          <div key={category} className="bg-white shadow rounded-xl p-4">
            <h2 className="text-xl font-semibold mb-3">📁 {category}</h2>
            <ul className="list-disc list-inside">
              {files.map((file, idx) => (
                <li key={idx} className="mb-2">
                  <div className="font-medium text-gray-800">
                    Renamed: {file.renamed}
                  </div>
                  <div className="text-sm text-gray-600">
                    Original: {file.originalName}
                  </div>
                  <div className="text-sm text-gray-600">
                    Subcategory: {file.subcategory}
                  </div>
                  <details className="mt-1 text-sm">
                    <summary className="cursor-pointer text-blue-600">📄 Preview Text</summary>
                    <pre className="whitespace-pre-wrap mt-1 bg-gray-100 p-2 rounded">
                      {file.preview}
                    </pre>
                  </details>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </div>
  );
}
