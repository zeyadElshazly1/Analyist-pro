"use client";

import { useState } from "react";
import { uploadFile } from "@/lib/api";
import { Button } from "@/components/ui/button";

type Props = {
  projectId: number;
};

export function UploadDataset({ projectId }: Props) {
  const [file, setFile] = useState<File | null>(null);
  const [message, setMessage] = useState("");

  async function handleUpload() {
    if (!file) return;

    try {
      setMessage("Uploading...");

      await uploadFile(projectId, file);

      setMessage("Upload complete");
    } catch {
      setMessage("Upload failed");
    }
  }

  return (
    <div className="space-y-3">

      <input
        type="file"
        onChange={(e) =>
          setFile(e.target.files?.[0] || null)
        }
      />

      <Button onClick={handleUpload}>
        Upload dataset
      </Button>

      {message && (
        <p className="text-sm text-white/60">
          {message}
        </p>
      )}

    </div>
  );
}