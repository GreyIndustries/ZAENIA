export type ChatPhoto = { name: string; data: string };

/** Decode locally, reduce upload size and strip EXIF/location metadata. */
export async function preparePhoto(file: File): Promise<ChatPhoto> {
  if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) throw new Error('Choose a JPEG, PNG or WebP photo.');
  if (file.size > 20_000_000) throw new Error('Choose a photo smaller than 20 MB.');
  const url = URL.createObjectURL(file);
  try {
    const image = new Image(); image.src = url; await image.decode();
    if (!image.naturalWidth || image.naturalWidth * image.naturalHeight > 80_000_000) throw new Error('This photo is too large to open.');
    const scale = Math.min(1, 1600 / Math.max(image.naturalWidth, image.naturalHeight));
    const canvas = document.createElement('canvas');
    canvas.width = Math.max(1, Math.round(image.naturalWidth * scale));
    canvas.height = Math.max(1, Math.round(image.naturalHeight * scale));
    const ctx = canvas.getContext('2d');
    if (!ctx) throw new Error('This photo could not be opened.');
    ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(image, 0, 0, canvas.width, canvas.height);
    const data = canvas.toDataURL('image/jpeg', .88);
    if (data.length > 2_800_000) throw new Error('This photo is too detailed. Try cropping it first.');
    return { name: file.name.slice(0, 120), data };
  } finally { URL.revokeObjectURL(url); }
}
