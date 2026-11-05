/**
 * Deterministic Server-Side Headless Renderer (Phase 2).
 * 
 * Streams Skia canvas frames at deterministic 30/60fps directly into FFmpeg's
 * stdin rawvideo pipe. Shares the exact same rendering logic as the browser WYSIWYG
 * canvas (`frontend/caption_canvas.js`) to guarantee strict 1:1 pixel parity.
 */

const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');
const { createCanvas, GlobalFonts } = require('@napi-rs/canvas');
const CaptionCanvasRenderer = require('../frontend/caption_canvas.js');
const StickerCompositor = require('../frontend/sticker_compositor.js');

// ── Font Registration ────────────────────────────────────────────────────────
const FONTS_DIR = path.resolve(__dirname, 'assets', 'fonts');

function registerFonts() {
  const fontDefinitions = [
    { file: 'Montserrat-Bold.ttf', family: 'Montserrat' },
    { file: 'Montserrat-Regular.ttf', family: 'Montserrat' },
    { file: 'Merriweather-Bold.ttf', family: 'Merriweather' },
    { file: 'Merriweather-Regular.ttf', family: 'Merriweather' },
    { file: 'JetBrainsMono-Bold.ttf', family: 'JetBrains Mono' },
    { file: 'JetBrainsMono-Regular.ttf', family: 'JetBrains Mono' },
    { file: 'Anton-Regular.ttf', family: 'Anton' },
    { file: 'BebasNeue-Regular.ttf', family: 'Bebas Neue' },
    { file: 'KomikaAxis.ttf', family: 'Komika Axis' },
    { file: 'Syne-Bold.ttf', family: 'Syne' },
    { file: 'TheBoldFont.ttf', family: 'The Bold Font' },
  ];

  for (const def of fontDefinitions) {
    const fontPath = path.join(FONTS_DIR, def.file);
    if (fs.existsSync(fontPath)) {
      try {
        GlobalFonts.registerFromPath(fontPath, def.family);
      } catch (err) {
        console.warn(`[render_headless] Warning: failed to register ${def.file}:`, err.message);
      }
    }
  }
}

registerFonts();

// ── Argument Parsing ─────────────────────────────────────────────────────────
function parseArgs() {
  const args = process.argv.slice(2);
  const options = {
    timelinePath: '',
    sourcePath: '',
    outputPath: '',
    start: 0.0,
    duration: 5.0,
    width: 1080,
    height: 1920,
    fps: 30,
    crf: 21,
    preset: 'veryfast',
    fitMode: 'blur',
  };

  for (let i = 0; i < args.length; i++) {
    switch (args[i]) {
      case '--timeline':
        options.timelinePath = args[++i];
        break;
      case '--source':
        options.sourcePath = args[++i];
        break;
      case '--output':
        options.outputPath = args[++i];
        break;
      case '--start':
        options.start = parseFloat(args[++i]);
        break;
      case '--duration':
        options.duration = parseFloat(args[++i]);
        break;
      case '--width':
        options.width = parseInt(args[++i], 10);
        break;
      case '--height':
        options.height = parseInt(args[++i], 10);
        break;
      case '--fps':
        options.fps = parseInt(args[++i], 10);
        break;
      case '--fit-mode':
        options.fitMode = args[++i];
        break;
      case '--crf':
        options.crf = parseInt(args[++i], 10);
        break;
      case '--preset':
        options.preset = args[++i];
        break;
    }
  }

  return options;
}

// ── Headless Render Pipeline ─────────────────────────────────────────────────
async function renderVideo() {
  const opts = parseArgs();

  if (!opts.timelinePath || !fs.existsSync(opts.timelinePath)) {
    console.error('[render_headless] Error: Missing or invalid --timeline file.');
    process.exit(1);
  }
  if (!opts.sourcePath || !fs.existsSync(opts.sourcePath)) {
    console.error('[render_headless] Error: Missing or invalid --source video.');
    process.exit(1);
  }
  if (!opts.outputPath) {
    console.error('[render_headless] Error: Missing --output path.');
    process.exit(1);
  }

  const rawTimeline = fs.readFileSync(opts.timelinePath, 'utf8');
  const timeline = JSON.parse(rawTimeline);

  const width = opts.width;
  const height = opts.height;
  const fps = opts.fps;
  const startSec = opts.start;
  const durationSec = opts.duration;
  const totalFrames = Math.max(1, Math.round(durationSec * fps));

  console.log(`[render_headless] Starting headless render: ${totalFrames} frames @ ${fps}fps (${width}x${height})`);

  // Ensure output directory exists
  const outDir = path.dirname(path.resolve(opts.outputPath));
  if (!fs.existsSync(outDir)) {
    fs.mkdirSync(outDir, { recursive: true });
  }

  // Build FFmpeg video compositing filtergraph matching Cutflow presets
  // Input 0: stdin rawvideo RGBA (canvas frames)
  // Input 1: source video
  const blurRadius = (width === 1080 && height === 1920) ? '28:5' : '24:4';
  const dimAmount = (width === 1080 && height === 1920) ? '-0.12' : '-0.10';

  let filterGraph = '';
  if (opts.fitMode === 'letterbox') {
    filterGraph = `[1:v]scale=${width}:${height}:force_original_aspect_ratio=decrease,pad=${width}:${height}:(ow-iw)/2:(oh-ih)/2:color=black[bg];[bg][0:v]overlay=0:0[vout]`;
  } else if (opts.fitMode === 'crop') {
    filterGraph = `[1:v]scale=${width}:${height}:force_original_aspect_ratio=increase,crop=${width}:${height}[bg];[bg][0:v]overlay=0:0[vout]`;
  } else {
    // Ambient Blur mode (default)
    filterGraph = `[1:v]scale=${width}:${height}:force_original_aspect_ratio=increase,crop=${width}:${height},boxblur=${blurRadius},eq=brightness=${dimAmount}:contrast=1.06[bg];[1:v]scale=${width}:-2:flags=lanczos[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2[base];[base][0:v]overlay=0:0[vout]`;
  }

  // Phase 5 Audio SFX Sub-Mixer Filtergraph
  const sfxDir = path.resolve(__dirname, 'assets', 'sfx');
  const audioSfx = timeline.audio_sfx || [];
  const clipStartMs = startSec * 1000.0;
  const clipEndMs = (startSec + durationSec) * 1000.0;
  const validSfx = audioSfx.filter(ev => {
    const t = ev.timestamp_ms || 0;
    return t >= clipStartMs && t <= clipEndMs;
  });

  const sfxInputs = [];
  const sfxTypeToInputIdx = {};
  let nextInputIdx = 2; // Input 0 is rawvideo pipe, Input 1 is source video

  if (validSfx.length > 0) {
    const usedTypes = [...new Set(validSfx.map(ev => ev.type))].sort();
    for (const stype of usedTypes) {
      const sfxPath = path.join(sfxDir, `${stype}.wav`);
      if (fs.existsSync(sfxPath)) {
        sfxTypeToInputIdx[stype] = nextInputIdx++;
        sfxInputs.push('-i', sfxPath);
      }
    }
  }

  let audioFilterGraph = '';
  let audioMapTarget = '1:a?';

  if (sfxInputs.length > 0) {
    const filterChains = [];
    const mixLabels = ['[1:a]'];

    validSfx.forEach((ev, idx) => {
      const inputIdx = sfxTypeToInputIdx[ev.type];
      if (inputIdx !== undefined) {
        const delayMs = Math.max(0, Math.round(ev.timestamp_ms - clipStartMs));
        const vol = (ev.volume !== undefined ? ev.volume : 0.75).toFixed(2);
        const outLbl = `sfx_${idx}`;
        filterChains.push(`[${inputIdx}:a]adelay=${delayMs}|${delayMs},volume=${vol}[${outLbl}]`);
        mixLabels.push(`[${outLbl}]`);
      }
    });

    if (mixLabels.length > 1) {
      filterChains.push(`${mixLabels.join('')}amix=inputs=${mixLabels.length}:dropout_transition=0:normalize=0[aout]`);
      audioFilterGraph = ';' + filterChains.join(';');
      audioMapTarget = '[aout]';
    }
  }

  const ffmpegArgs = [
    '-hide_banner',
    '-loglevel', 'error',
    '-y',
    // Input 0: Raw RGBA video stream from stdin
    '-f', 'rawvideo',
    '-pix_fmt', 'rgba',
    '-s', `${width}x${height}`,
    '-r', `${fps}`,
    '-i', 'pipe:0',
    // Input 1: Source video clipped to time window
    '-ss', `${startSec.toFixed(3)}`,
    '-i', opts.sourcePath,
    '-t', `${durationSec.toFixed(3)}`,
    ...sfxInputs,
    // Composite overlay and audio filter
    '-filter_complex', `${filterGraph}${audioFilterGraph}`,
    '-map', '[vout]',
    '-map', audioMapTarget,
    '-c:v', 'libx264',
    '-preset', opts.preset,
    '-crf', `${opts.crf}`,
    '-c:a', 'aac',
    '-b:a', '160k',
    '-pix_fmt', 'yuv420p',
    '-movflags', '+faststart',
    opts.outputPath,
  ];

  // Preload all vector sticker assets in Skia before drawing
  await StickerCompositor.preloadAll();

  const ffmpegProc = spawn('ffmpeg', ffmpegArgs, { stdio: ['pipe', 'inherit', 'inherit'] });

  const canvas = createCanvas(width, height);
  const ctx = canvas.getContext('2d');

  let frameIdx = 0;

  function writeNextFrame() {
    while (frameIdx < totalFrames) {
      const currentTimeSec = startSec + (frameIdx / fps);
      CaptionCanvasRenderer.renderFrame(ctx, timeline, currentTimeSec, width, height);

      // Extract raw RGBA pixel buffer
      const imgData = ctx.getImageData(0, 0, width, height);
      const buffer = Buffer.from(imgData.data.buffer);

      frameIdx++;
      const canContinue = ffmpegProc.stdin.write(buffer);
      if (!canContinue) {
        // Backpressure: pause and wait for drain event
        ffmpegProc.stdin.once('drain', writeNextFrame);
        return;
      }
    }

    // Finished writing all frames
    ffmpegProc.stdin.end();
  }

  ffmpegProc.on('error', (err) => {
    console.error('[render_headless] FFmpeg spawn error:', err);
    process.exit(1);
  });

  return new Promise((resolve, reject) => {
    ffmpegProc.on('close', (code) => {
      if (code === 0) {
        console.log(`[render_headless] Export succeeded: ${opts.outputPath}`);
        resolve();
      } else {
        reject(new Error(`FFmpeg exited with code ${code}`));
      }
    });

    writeNextFrame();
  });
}

if (require.main === module) {
  renderVideo().catch((err) => {
    console.error('[render_headless] Fatal error:', err);
    process.exit(1);
  });
}

