export type ChatFile = { name: string; size: number; data: string };

export const MAX_SHARED_FILES = 4;
const MAX_FILE_BYTES = 15_000_000;

/** Read a file to share with ZAE (base64, no data: prefix). */
export function readSharedFile(file: File): Promise<ChatFile> {
  if (file.size > MAX_FILE_BYTES) return Promise.reject(new Error(`${file.name} is larger than 15 MB.`));
  if (file.size === 0) return Promise.reject(new Error(`${file.name} is empty.`));
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const url = String(reader.result || "");
      resolve({ name: file.name.slice(0, 120), size: file.size, data: url.slice(url.indexOf(",") + 1) });
    };
    reader.onerror = () => reject(new Error(`${file.name} could not be read.`));
    reader.readAsDataURL(file);
  });
}

export function fileSize(bytes: number): string {
  return bytes < 1024 ? `${bytes} B` : bytes < 1_048_576 ? `${Math.round(bytes / 1024)} KB` : `${(bytes / 1_048_576).toFixed(1)} MB`;
}
