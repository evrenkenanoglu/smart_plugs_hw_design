import { createHash } from 'node:crypto';
import { access, mkdir, readFile, rename, rmdir, stat, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const SCRIPT_DIR = path.dirname(fileURLToPath(import.meta.url));
const EMC_ROOT = path.resolve(SCRIPT_DIR, '..');
const APP_ROOT = path.join(EMC_ROOT, 'smart_power_strip');
const LOCKED_ROOT = path.join(APP_ROOT, 'inputs', 'locked_rev');
const MANIFEST_PATH = path.join(
  APP_ROOT,
  'configs',
  'revision_manifest.json',
);
const DEFAULT_PACKAGE_ROOT = String.raw`C:\Users\Evren\AppData\Local\Tools\easyeda-mcp-pro-1.16.0\node_modules\easyeda-mcp-pro`;
const REQUIRED_TOOLS = [
  'easyeda_health_check',
  'easyeda_project_list',
  'easyeda_schematic_sheet_info',
  'easyeda_pcb_components',
  'easyeda_board_layers',
  'easyeda_board_stackup',
  'easyeda_board_dimensions',
  'easyeda_export_gerbers',
  'easyeda_bom_export',
  'easyeda_export_pick_place',
  'easyeda_export_netlist',
  'easyeda_export_pdf',
];
const REQUIRED_EXPORTS = [
  'gerbers',
  'bom',
  'pick_place',
  'netlist',
  'board_pdf',
  'schematic_pdf',
];
const BOARD_SIGNATURES = {
  MAIN_OMRON: {
    references: ['CN1', 'U1', 'L1', 'FH1', 'RV1', 'K1', 'K2', 'K3', 'K4'],
    deviceMarkers: [['U1', 'HLK-5LS05']],
  },
  UI: {
    references: ['CN1', 'U1', 'U2', 'SW1', 'SW2', 'SW3', 'SW4'],
    deviceMarkers: [
      ['U1', 'AMS1117'],
      ['U2', 'ESP32-C6-WROOM-1'],
    ],
  },
};

class ContextDriftError extends Error {}

function usage() {
  return [
    'Usage: node emc\\tools\\export_easyeda_board.mjs --board MAIN_OMRON|UI [--output <folder>] [--allow-unlisted-active-project]',
    '',
    'Exports a read-only candidate bundle into a unique folder under',
    'emc\\smart_power_strip\\inputs\\locked_rev\\<board>\\.',
    'The script refuses to export unless the active project and focused PCB',
    'can be matched to the requested board. It never sets locked=true.',
    'The unlisted-project override produces candidates only and never updates the revision manifest.',
  ].join('\n');
}

function parseArgs(argv) {
  const parsed = { board: null, output: null, help: false, allowUnlistedActiveProject: false };
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === '--help' || arg === '-h') {
      parsed.help = true;
    } else if (arg === '--board') {
      parsed.board = argv[++index];
    } else if (arg === '--output') {
      parsed.output = argv[++index];
    } else if (arg === '--allow-unlisted-active-project') {
      parsed.allowUnlistedActiveProject = true;
    } else {
      throw new Error(`Unknown argument: ${arg}`);
    }
  }
  if (parsed.help) return parsed;
  if (!Object.hasOwn(BOARD_SIGNATURES, parsed.board)) {
    throw new Error('--board must be MAIN_OMRON or UI');
  }
  return parsed;
}

function isWithin(parent, candidate) {
  const relative = path.relative(parent, candidate);
  return relative !== '' && !relative.startsWith(`..${path.sep}`) && relative !== '..' && !path.isAbsolute(relative);
}

function stableStringify(value) {
  if (Array.isArray(value)) {
    return `[${value.map(stableStringify).join(',')}]`;
  }
  if (value && typeof value === 'object') {
    const entries = Object.keys(value)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${stableStringify(value[key])}`);
    return `{${entries.join(',')}}`;
  }
  return JSON.stringify(value);
}

function parseToolResult(result, toolName) {
  if (result.isError) {
    const text = (result.content ?? [])
      .filter((entry) => entry.type === 'text')
      .map((entry) => entry.text)
      .join('\n');
    throw new Error(`${toolName} failed: ${text || 'MCP tool returned an error'}`);
  }
  if (result.structuredContent && typeof result.structuredContent === 'object') {
    return result.structuredContent;
  }
  const text = (result.content ?? [])
    .filter((entry) => entry.type === 'text')
    .map((entry) => entry.text)
    .join('\n')
    .trim();
  if (!text) throw new Error(`${toolName} returned no structured or text result`);
  try {
    return JSON.parse(text);
  } catch {
    return { text };
  }
}

async function callTool(client, name, args = {}, options = {}) {
  const result = await client.callTool(
    { name, arguments: args },
    { timeout: options.timeout ?? 20_000 },
  );
  const payload = parseToolResult(result, name);
  if (!options.allowUnavailable && payload.not_available === true) {
    throw new Error(`${name} is unavailable: ${payload.error ?? 'no details returned'}`);
  }
  if (!options.allowUnavailable && payload.error) {
    throw new Error(`${name} failed: ${payload.error}`);
  }
  return payload;
}

function assertListedActiveProject(projectList, projectId, allowUnlisted = false) {
  if (projectList.complete !== true || !Array.isArray(projectList.projects)) {
    throw new Error('Project listing is incomplete; no export was attempted.');
  }
  if (projectList.activeProjectId !== projectId) {
    throw new ContextDriftError('The active EasyEDA project changed during export.');
  }
  if (projectList.projects.some((project) => project.active === true && project.projectId !== projectId)) {
    throw new Error('Project list contains a conflicting active project; no export was attempted.');
  }
  const matching = projectList.projects.filter((project) => project.projectId === projectId);
  if (matching.length === 0) {
    if (allowUnlisted) return { project: null, unlisted: true };
    throw new Error(
      `Active project ID ${projectId} is absent from the active project entries; no export was attempted.`,
    );
  }
  if (matching.length !== 1 || matching[0].active !== true) {
    throw new Error('Listed active project identity is conflicting; no export was attempted.');
  }
  const active = matching[0];
  if (typeof active.name !== 'string' || active.name.trim().toLowerCase() !== 'smart_plugs') {
    throw new Error(
      `Active project is ${JSON.stringify(active.name)}, not Smart_Plugs; no export was attempted.`,
    );
  }
  return { project: active, unlisted: false };
}

function assertRequestedBoardFocus(sheetInfo, board, projectId) {
  if (sheetInfo.not_available === true || !sheetInfo.focused_document) {
    throw new Error(
      `Focused PCB identity is unavailable: ${sheetInfo.error ?? 'missing focused_document'}`,
    );
  }
  const document = sheetInfo.focused_document;
  const name = typeof document.name === 'string' ? document.name.trim().toUpperCase() : '';
  if (document.documentType !== 3 || ![board, `PCB_${board}`].includes(name) ||
      typeof document.uuid !== 'string' || !document.uuid.trim()) {
    throw new Error(
      `Focused document does not identify a PCB named ${board}: ${JSON.stringify(document)}`,
    );
  }
  if (sheetInfo.project_id !== projectId || document.parentProjectUuid !== projectId) {
    throw new Error('Focused PCB parent project identity is unavailable or does not match the active project.');
  }
  const pagesText = JSON.stringify(sheetInfo.pages ?? []).toLowerCase();
  if (!pagesText.includes(board.toLowerCase())) {
    throw new Error(`Project page metadata does not map a schematic to ${board}.`);
  }
  return {
    document: sheetInfo.focused_document,
    key: stableStringify(sheetInfo.focused_document),
  };
}

function assertBoardSignature(payload, board) {
  if (!Number.isInteger(payload.total) || payload.total <= 0 ||
      !Array.isArray(payload.components) || payload.total !== payload.components.length) {
    throw new Error(`Complete PCB components were not returned for ${board}.`);
  }
  const byReference = new Map(
    payload.components.map((component) => [
      String(component.designator ?? '').toUpperCase(),
      component,
    ]),
  );
  if (byReference.size !== payload.total || byReference.has('')) {
    throw new Error(`PCB component references for ${board} are missing or duplicated.`);
  }
  const signature = BOARD_SIGNATURES[board];
  const missing = signature.references.filter(
    (reference) => !byReference.has(reference),
  );
  if (missing.length) {
    throw new Error(
      `Focused PCB does not match ${board}; expected component references are missing: ${missing.join(', ')}`,
    );
  }
  for (const [reference, marker] of signature.deviceMarkers) {
    const device = String(byReference.get(reference)?.deviceName ?? '').toLowerCase();
    if (!device.includes(marker.toLowerCase())) {
      throw new Error(
        `Focused PCB does not match ${board}; ${reference} device marker ${JSON.stringify(marker)} was not found.`,
      );
    }
  }
  return {
    component_count: payload.total,
    references: [...byReference.keys()].sort(),
    components_key: stableStringify(payload.components.map(stableStringify).sort()),
  };
}

async function ensureContext(client, { projectId, board, focusIdentity, boardSignature, unlisted }) {
  try {
    const currentList = await callTool(client, 'easyeda_project_list');
    const currentProject = assertListedActiveProject(currentList, projectId, unlisted);
    if (currentProject.unlisted !== unlisted) {
      throw new Error('Active project listing status changed.');
    }
    const sheetInfo = await callTool(
      client, 'easyeda_schematic_sheet_info', { projectId, scope: 'all_pages' },
    );
    const focus = assertRequestedBoardFocus(sheetInfo, board, projectId);
    if (focus.key !== focusIdentity.key) throw new Error('Focused PCB identity changed.');
    const components = await callTool(
      client, 'easyeda_pcb_components', { projectId, limit: 200, offset: 0 },
    );
    if (stableStringify(assertBoardSignature(components, board)) !== stableStringify(boardSignature)) {
      throw new Error('PCB component signature changed.');
    }
    return sheetInfo;
  } catch (error) {
    throw new ContextDriftError(`Context verification failed; stopping exports: ${error.message}`);
  }
}

async function sha256File(filePath) {
  const bytes = await readFile(filePath);
  return createHash('sha256').update(bytes).digest('hex');
}

async function writeJson(filePath, value) {
  await writeFile(filePath, `${JSON.stringify(value, null, 2)}\n`, 'utf8');
}

async function validateExport(filePath, kind) {
  const info = await stat(filePath);
  if (!info.isFile() || info.size === 0) {
    throw new Error(`${kind} export is empty or not a regular file: ${filePath}`);
  }
  const bytes = await readFile(filePath);
  if (kind === 'gerbers' && !(bytes[0] === 0x50 && bytes[1] === 0x4b)) {
    throw new Error('Gerber export is not a ZIP archive.');
  }
  if (kind.endsWith('_pdf') && !bytes.subarray(0, 1024).includes(Buffer.from('%PDF-'))) {
    throw new Error(`${kind} export does not have a PDF signature.`);
  }
  if (kind === 'bom' || kind === 'pick_place') {
    const text = bytes.toString('utf8').replace(/^\uFEFF/, '');
    if (text.trim().split(/\r?\n/).length < 2) {
      throw new Error(`${kind} export has no data rows.`);
    }
  }
  if (kind === 'netlist' && bytes.toString('utf8').trim().length === 0) {
    throw new Error('Netlist export is empty.');
  }
  return { bytes: info.size };
}

async function maybeUpdateRevisionManifest({
  projectId,
  baseManifestHash,
  hashedFiles,
  complete,
  unlistedOverrideUsed = false,
}) {
  if (unlistedOverrideUsed) {
    return {
      updated: false,
      reason: 'Active project was unlisted; candidate exports cannot update the revision manifest.',
    };
  }
  if (!complete) {
    return {
      updated: false,
      reason: 'Required exports are incomplete; the revision manifest was not changed.',
    };
  }
  const manifestBytes = await readFile(MANIFEST_PATH);
  if (createHash('sha256').update(manifestBytes).digest('hex') !== baseManifestHash) {
    return {
      updated: false,
      reason: 'The revision manifest changed during export; preserving the newer file.',
    };
  }
  const manifest = JSON.parse(manifestBytes.toString('utf8'));
  if (manifest.project_id !== projectId) {
    return {
      updated: false,
      reason: 'Active project ID differs from revision_manifest.json; candidate hashes remain in export_manifest.json.',
    };
  }
  if (manifest.revision === 'UNCONFIRMED' || !manifest.revision) {
    return {
      updated: false,
      reason: 'Source revision is unconfirmed; candidate hashes remain in export_manifest.json.',
    };
  }

  const entries = new Map(
    (manifest.files ?? []).map((entry) => [entry.path.toLowerCase(), entry]),
  );
  for (const file of hashedFiles) {
    const relativePath = path.relative(APP_ROOT, file.absolute_path).split(path.sep).join('/');
    entries.set(relativePath.toLowerCase(), {
      path: relativePath,
      sha256: file.sha256,
    });
  }
  manifest.files = [...entries.values()].sort((left, right) =>
    left.path.localeCompare(right.path),
  );
  manifest.locked = false;
  const temporaryPath = `${MANIFEST_PATH}.tmp-${process.pid}`;
  await writeJson(temporaryPath, manifest);
  await rename(temporaryPath, MANIFEST_PATH);
  return {
    updated: true,
    locked: false,
    reason: 'Hashes were added for the confirmed project/revision; manual Stage 0 review is still required.',
  };
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help) {
    console.log(usage());
    return 0;
  }

  const board = args.board;
  const boardDirectory = path.join(LOCKED_ROOT, board);
  const stamp = new Date().toISOString().replaceAll(/[-:.]/g, '').replace('T', '_').replace('Z', '');
  const defaultOutput = path.join(boardDirectory, `MCP_AUTO_${stamp}`);
  const outputDirectory = path.resolve(args.output ?? defaultOutput);
  if (!isWithin(LOCKED_ROOT, outputDirectory)) {
    throw new Error(`Output must be a new folder under ${LOCKED_ROOT}`);
  }
  try {
    await access(outputDirectory);
    throw new Error(`Output folder already exists; refusing to overwrite: ${outputDirectory}`);
  } catch (error) {
    if (error.code !== 'ENOENT') throw error;
  }

  const packageRoot =
    process.env.EASYEDA_MCP_PRO_PACKAGE_ROOT ?? DEFAULT_PACKAGE_ROOT;
  const serverEntry = path.join(packageRoot, 'dist', 'index.js');
  const sdkRoot = path.resolve(packageRoot, '..', '@modelcontextprotocol', 'client');
  await access(serverEntry);
  await access(path.join(sdkRoot, 'dist', 'index.mjs'));
  await mkdir(outputDirectory, { recursive: false });

  const baseManifestHash = await sha256File(MANIFEST_PATH);
  let client;
  let clientConnected = false;
  let transport;
  let serverStderr = '';
  let exportsStarted = false;
  const results = {};
  const files = [];
  let project;
  let projectId;
  let unlistedOverrideUsed = false;
  let focusIdentity;
  let boardSignature;
  let identityData;
  let metadata = {};
  let fatalExportError = null;

  try {
    const [{ Client }, { StdioClientTransport, getDefaultEnvironment }] =
      await Promise.all([
        import(pathToFileURL(path.join(sdkRoot, 'dist', 'index.mjs')).href),
        import(pathToFileURL(path.join(sdkRoot, 'dist', 'stdio.mjs')).href),
      ]);
    const env = {
      ...getDefaultEnvironment(),
      ARTIFACT_DIR: outputDirectory,
      BRIDGE_WAIT_FOR_EDA_MS: '3000',
      LOG_LEVEL: 'error',
      TOOL_PROFILE: 'pro',
      TRANSPORT: 'stdio',
    };
    transport = new StdioClientTransport({
      command: process.execPath,
      args: [serverEntry],
      cwd: packageRoot,
      env,
      stderr: 'pipe',
    });
    transport.stderr?.on('data', (chunk) => {
      serverStderr += chunk.toString();
    });
    client = new Client(
      { name: 'easyeda-board-export', version: '1.0.0' },
      { capabilities: {} },
    );
    await client.connect(transport);
    clientConnected = true;
    const { tools } = await client.listTools();
    const availableTools = new Set(tools.map((tool) => tool.name));
    const missingTools = REQUIRED_TOOLS.filter((name) => !availableTools.has(name));
    if (missingTools.length) {
      throw new Error(`Installed MCP profile is missing required tools: ${missingTools.join(', ')}`);
    }

    const health = await callTool(client, 'easyeda_health_check');
    if (health.status !== 'ok' || health.bridge_connected !== true) {
      throw new Error(
        `EasyEDA bridge is not connected (status=${health.status ?? 'unknown'}, bridge_connected=${health.bridge_connected ?? 'unknown'}).`,
      );
    }
    const projectList = await callTool(client, 'easyeda_project_list');
    projectId = projectList.activeProjectId;
    if (typeof projectId !== 'string' || !projectId) {
      throw new Error('EasyEDA did not report an active project ID.');
    }
    const projectCheck = assertListedActiveProject(projectList, projectId, args.allowUnlistedActiveProject);
    project = projectCheck.project;
    unlistedOverrideUsed = projectCheck.unlisted;

    const initialSheetInfo = await callTool(
      client,
      'easyeda_schematic_sheet_info',
      { projectId, scope: 'all_pages' },
    );
    focusIdentity = assertRequestedBoardFocus(initialSheetInfo, board, projectId);
    const componentPayload = await callTool(
      client,
      'easyeda_pcb_components',
      { projectId, limit: 200, offset: 0 },
    );
    boardSignature = assertBoardSignature(componentPayload, board);

    identityData = {
      project_id: projectId,
      project_name: project?.name ?? null,
      active_project_list_complete: projectList.complete,
      active_project_unlisted_override_used: unlistedOverrideUsed,
      focused_document: focusIdentity.document,
      requested_board: board,
      component_signature: boardSignature,
      schematic_page_metadata: initialSheetInfo.pages,
      source_revision_linked: false,
    };
    await writeJson(path.join(outputDirectory, 'Identity.json'), identityData);

    const checkContext = () => ensureContext(client, {
      projectId, board, focusIdentity, boardSignature, unlisted: unlistedOverrideUsed,
    });

    await checkContext();
    metadata.layers = await callTool(
      client,
      'easyeda_board_layers',
      { projectId },
      { allowUnavailable: true },
    );
    await checkContext();
    metadata.stackup = await callTool(
      client,
      'easyeda_board_stackup',
      { projectId },
      { allowUnavailable: true },
    );
    await checkContext();
    metadata.dimensions = await callTool(
      client,
      'easyeda_board_dimensions',
      { projectId },
      { allowUnavailable: true },
    );
    await writeJson(path.join(outputDirectory, 'BoardLayers.json'), metadata.layers);
    await writeJson(path.join(outputDirectory, 'Stackup.json'), metadata.stackup);
    await writeJson(path.join(outputDirectory, 'BoardDimensions.json'), metadata.dimensions);

    const exportSpecs = [
      {
        key: 'gerbers',
        tool: 'easyeda_export_gerbers',
        filename: 'Gerbers.zip',
        args: { drillFormat: 'millimeter', filePath: path.join(outputDirectory, 'Gerbers.zip') },
      },
      {
        key: 'bom',
        tool: 'easyeda_bom_export',
        filename: 'BOM.csv',
        args: { format: 'csv', filePath: path.join(outputDirectory, 'BOM.csv') },
      },
      {
        key: 'pick_place',
        tool: 'easyeda_export_pick_place',
        filename: 'PickAndPlace.csv',
        args: { format: 'csv', filePath: path.join(outputDirectory, 'PickAndPlace.csv') },
      },
      {
        key: 'netlist',
        tool: 'easyeda_export_netlist',
        filename: 'Netlist.pads',
        args: { format: 'pads', filePath: path.join(outputDirectory, 'Netlist.pads') },
      },
      {
        key: 'board_pdf',
        tool: 'easyeda_export_pdf',
        filename: 'PCB_Layout.pdf',
        args: {
          scope: 'board',
          orientation: 'landscape',
          filePath: path.join(outputDirectory, 'PCB_Layout.pdf'),
        },
      },
      {
        key: 'schematic_pdf',
        tool: 'easyeda_export_pdf',
        filename: 'Schematic.pdf',
        args: {
          scope: 'schematic',
          orientation: 'landscape',
          filePath: path.join(outputDirectory, 'Schematic.pdf'),
        },
        timeout: 25_000,
      },
    ];

    for (const spec of exportSpecs) {
      try {
        await checkContext();
        exportsStarted = true;
        const payload = await callTool(
          client,
          spec.tool,
          { projectId, ...spec.args },
          { timeout: spec.timeout ?? 20_000 },
        );
        if (payload.exported !== true) {
          throw new Error(payload.error ?? 'MCP did not confirm export success.');
        }
        const returnedPath =
          payload.artifact_path ?? payload.file_path ?? spec.args.filePath;
        const absolutePath = path.isAbsolute(returnedPath)
          ? path.resolve(returnedPath)
          : path.resolve(outputDirectory, returnedPath);
        if (!isWithin(outputDirectory, absolutePath)) {
          throw new Error(`MCP returned a path outside the export folder: ${returnedPath}`);
        }
        const validation = await validateExport(absolutePath, spec.key);
        results[spec.key] = {
          status: 'exported',
          file: path.basename(absolutePath),
          bytes: validation.bytes,
          response: payload,
        };
        files.push({ absolute_path: absolutePath });
      } catch (error) {
        results[spec.key] = {
          status: 'failed',
          error: error.message,
        };
        if (error instanceof ContextDriftError) {
          fatalExportError = error.message;
          break;
        }
      }
      if (!fatalExportError) {
        try {
          await checkContext();
        } catch (error) {
          fatalExportError = error.message;
        }
      }
    }
  } catch (error) {
    if (!exportsStarted) {
      try {
        await rmdir(outputDirectory);
      } catch (cleanupError) {
        if (cleanupError.code !== 'ENOTEMPTY') {
          console.error(`Could not remove empty failed-preflight folder: ${cleanupError.message}`);
        }
      }
    }
    throw new Error(
      `${error.message}${serverStderr.trim() ? `\nMCP server: ${serverStderr.trim()}` : ''}`,
    );
  } finally {
    if (clientConnected) {
      await client.close();
    } else if (transport?.pid) {
      await transport.close();
    }
  }

  for (const filename of ['Identity.json', 'BoardLayers.json', 'Stackup.json', 'BoardDimensions.json']) {
    const absolutePath = path.join(outputDirectory, filename);
    try {
      await access(absolutePath);
      files.push({ absolute_path: absolutePath });
    } catch (error) {
      if (error.code !== 'ENOENT') throw error;
    }
  }
  const hashedFiles = [];
  for (const file of files) {
    const info = await stat(file.absolute_path);
    hashedFiles.push({
      path: path.relative(outputDirectory, file.absolute_path).split(path.sep).join('/'),
      absolute_path: file.absolute_path,
      bytes: info.size,
      sha256: await sha256File(file.absolute_path),
    });
  }
  const complete = !fatalExportError && REQUIRED_EXPORTS.every(
    (key) => results[key]?.status === 'exported',
  );
  const revisionManifestUpdate = await maybeUpdateRevisionManifest({
    projectId,
    baseManifestHash,
    hashedFiles,
    complete,
    unlistedOverrideUsed,
  });
  const exportManifest = {
    schema_version: 1,
    generated_at_utc: new Date().toISOString(),
    requested_board: board,
    project: {
      id: projectId,
      name: project?.name ?? null,
      active_project_unlisted_override_used: unlistedOverrideUsed,
    },
    focused_document: identityData?.focused_document,
    component_signature: boardSignature,
    export_settings: {
      drill_format_requested: 'millimeter',
      pick_and_place_coordinate_units: 'not selectable in MCP schema; verify from output/settings',
      gerber_units: 'not independently verified by this script',
      netlist_kind: 'inspect the file header; do not assume schematic rather than PCB connectivity',
      schematic_pdf_content_reviewed: false,
    },
    metadata_files: {
      layers: 'BoardLayers.json',
      stackup: 'Stackup.json',
      dimensions: 'BoardDimensions.json',
    },
    exports: results,
    files: hashedFiles.map(({ path: relativePath, bytes, sha256 }) => ({
      path: relativePath,
      bytes,
      sha256,
    })),
    stage0_locked: false,
    source_revision_linked: false,
    revision_manifest_update: revisionManifestUpdate,
    fatal_export_error: fatalExportError,
    unresolved: [
      ...(unlistedOverrideUsed ? [
        'The complete project listing omitted the active project ID; this is an unverified candidate only.',
      ] : []),
      'Linkage between the live project and the supplied native archive must be confirmed.',
      'Verify PDF content, CSV designator/MPN completeness, Gerber/drill contents and units, and netlist scope.',
      'Fabricator-confirmed thickness, copper weight, dielectric data, and NPTH intent remain designer inputs.',
    ],
  };
  await writeJson(path.join(outputDirectory, 'export_manifest.json'), exportManifest);

  console.log(
    JSON.stringify(
      {
        status: complete ? 'candidate_bundle_exported' : 'partial_candidate_bundle',
        output_directory: outputDirectory,
        revision_manifest_updated: revisionManifestUpdate.updated,
        revision_manifest_locked: revisionManifestUpdate.updated ? false : null,
        failures: Object.fromEntries(
          Object.entries(results)
            .filter(([, result]) => result.status !== 'exported')
            .map(([key, result]) => [key, result.error]),
        ),
        note: 'This script never sets locked=true and its exports are not compliance or safety evidence.',
      },
      null,
      2,
    ),
  );
  return complete ? 0 : 1;
}

export {
  assertBoardSignature, assertListedActiveProject, assertRequestedBoardFocus,
  ContextDriftError, ensureContext, maybeUpdateRevisionManifest, parseArgs,
};

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    process.exitCode = await main();
  } catch (error) {
    console.error(`EasyEDA export aborted: ${error.message}`);
    process.exitCode = 2;
  }
}
