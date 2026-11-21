#!/usr/bin/env node
/**
 * Vercel Blob client token authorization helper.
 * Generates scoped client upload tokens for direct browser-to-blob uploads.
 */

const { handleUpload } = require('@vercel/blob/client');

async function main() {
  const token = process.env.BLOB_READ_WRITE_TOKEN;
  if (!token) {
    process.stderr.write(JSON.stringify({ error: 'BLOB_READ_WRITE_TOKEN not configured' }));
    process.exit(1);
  }

  let raw = '';
  process.stdin.setEncoding('utf8');
  for await (const chunk of process.stdin) {
    raw += chunk;
  }

  let body;
  try {
    body = JSON.parse(raw);
  } catch (err) {
    process.stderr.write(JSON.stringify({ error: 'Invalid JSON body' }));
    process.exit(1);
  }

  try {
    const jsonResponse = await handleUpload({
      body,
      request: { headers: {} },
      token,
      onBeforeGenerateToken: async (pathname) => {
        return {
          allowedContentTypes: [
            'video/mp4', 'video/quicktime', 'video/x-matroska',
            'video/webm', 'video/x-m4v', 'video/x-msvideo',
            'application/octet-stream'
          ],
          maximumSizeInBytes: 1024 * 1024 * 1024 // 1 GB
        };
      },
      onUploadCompleted: async () => {}
    });

    process.stdout.write(JSON.stringify(jsonResponse));
  } catch (err) {
    process.stderr.write(JSON.stringify({ error: err.message }));
    process.exit(1);
  }
}

main();
