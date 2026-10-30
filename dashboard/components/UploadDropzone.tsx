"use client";

/** Pick or drop one video file. */

import { useRef, useState } from "react";

const ACCEPT = ".mp4,.mov,.avi,.mkv,.webm,video/*";

export default function UploadDropzone({ file, onFile }: { file: File | null; onFile: (file: File) => void }) {
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);

  return (
    <div
      className={`dropzone${over ? " is-over" : ""}${file ? " has-file" : ""}`}
      role="button"
      tabIndex={0}
      onClick={() => input.current?.click()}
      onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && input.current?.click()}
      onDragOver={(e) => {
        e.preventDefault();
        setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setOver(false);
        const dropped = e.dataTransfer.files[0];
        if (dropped) onFile(dropped);
      }}
    >
      <input
        ref={input}
        type="file"
        accept={ACCEPT}
        hidden
        onChange={(e) => e.target.files?.[0] && onFile(e.target.files[0])}
      />
      {file ? (
        <>
          <b>{file.name}</b>
          <span>{(file.size / 1024 / 1024).toFixed(1)} MB · click to choose another</span>
        </>
      ) : (
        <>
          <b>Drop a conveyor video here</b>
          <span>or click to choose · mp4, mov, avi, mkv, webm</span>
        </>
      )}
    </div>
  );
}
