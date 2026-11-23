import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdir, mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  assertBoardSignature, assertListedActiveProject, assertRequestedBoardFocus,
  ContextDriftError, ensureContext, maybeUpdateRevisionManifest, parseArgs,
  resolvePackageRoot,
} from '../tools/export_easyeda_board.mjs';

const projectId = 'project-1';
const board = 'MAIN_OMRON';
const listed = {
  complete: true, activeProjectId: projectId,
  projects: [{ projectId, name: 'Smart_Plugs', active: true }],
};
const unlisted = { complete: true, activeProjectId: projectId, projects: [] };
const sheet = {
  project_id: projectId,
  focused_document: {
    name: 'PCB_MAIN_OMRON', uuid: 'pcb-1', documentType: 3, parentProjectUuid: projectId,
  },
  pages: [{ name: 'MAIN_OMRON' }],
};
const components = {
  total: 9,
  components: ['CN1', 'U1', 'L1', 'FH1', 'RV1', 'K1', 'K2', 'K3', 'K4']
    .map((designator) => ({ designator, deviceName: designator === 'U1' ? 'HLK-5LS05' : 'part' })),
};
const baseline = {
  projectId, board, unlisted: true,
  focusIdentity: assertRequestedBoardFocus(sheet, board, projectId),
  boardSignature: assertBoardSignature(components, board),
};
function mockClient(overrides = {}) {
  const responses = {
    easyeda_project_list: unlisted,
    easyeda_schematic_sheet_info: sheet,
    easyeda_pcb_components: components,
    ...overrides,
  };
  return {
    async callTool({ name }) {
      return { structuredContent: responses[name] };
    },
  };
}

test('default is strict and override permits only a complete unlisted project', () => {
  assert.equal(parseArgs(['--board', board]).allowUnlistedActiveProject, false);
  assert.equal(parseArgs(['--board', board, '--allow-unlisted-active-project']).allowUnlistedActiveProject, true);
  assert.throws(() => assertListedActiveProject(unlisted, projectId), /absent/);
  assert.deepEqual(assertListedActiveProject(unlisted, projectId, true), { project: null, unlisted: true });
  assert.equal(assertListedActiveProject(listed, projectId, true).unlisted, false);
  assert.throws(() => assertListedActiveProject({ ...unlisted, complete: false }, projectId, true), /incomplete/);
  assert.throws(() => assertListedActiveProject({ ...unlisted, activeProjectId: 'other' }, projectId, true), /changed/);
  assert.throws(() => assertListedActiveProject({
    ...unlisted, projects: [{ projectId, name: 'Other', active: true }],
  }, projectId, true), /not Smart_Plugs/);
  assert.throws(() => assertListedActiveProject({
    ...unlisted, projects: [{ projectId, name: 'Smart_Plugs', active: false }],
  }, projectId, true), /conflicting/);
  assert.throws(() => assertListedActiveProject({
    ...unlisted, projects: [{ projectId: 'other', name: 'Other', active: true }],
  }, projectId, true), /conflicting/);
});

test('package resolution accepts a portable override only for the pinned package layout', async (t) => {
  const temporaryRoot = await mkdtemp(path.join(os.tmpdir(), 'easyeda-package-'));
  t.after(() => rm(temporaryRoot, { recursive: true, force: true }));
  const packageRoot = path.join(temporaryRoot, 'node_modules', 'easyeda-mcp-pro');
  const sdkRoot = path.join(temporaryRoot, 'node_modules', '@modelcontextprotocol', 'client');
  await mkdir(path.join(packageRoot, 'dist'), { recursive: true });
  await mkdir(path.join(sdkRoot, 'dist'), { recursive: true });
  await writeFile(
    path.join(packageRoot, 'package.json'),
    JSON.stringify({ name: 'easyeda-mcp-pro', version: '1.16.0' }),
  );
  await writeFile(path.join(packageRoot, 'dist', 'index.js'), '');
  await writeFile(path.join(sdkRoot, 'dist', 'index.mjs'), '');
  await writeFile(path.join(sdkRoot, 'dist', 'stdio.mjs'), '');

  assert.equal(
    await resolvePackageRoot({ EASYEDA_MCP_PRO_PACKAGE_ROOT: packageRoot }),
    packageRoot,
  );
  await writeFile(
    path.join(packageRoot, 'package.json'),
    JSON.stringify({ name: 'easyeda-mcp-pro', version: '1.17.0' }),
  );
  await assert.rejects(
    resolvePackageRoot({ EASYEDA_MCP_PRO_PACKAGE_ROOT: packageRoot }),
    /Expected easyeda-mcp-pro@1\.16\.0/,
  );
});

test('board name, native type, UUID, parent and complete signature are required', () => {
  for (const change of [
    { name: 'PCB_MAIN_OMRON_COPY' },
    { name: 'PCB_UI' },
    { name: undefined },
    { documentType: 1 },
    { uuid: '' },
    { parentProjectUuid: 'other' },
    { parentProjectUuid: undefined },
  ]) {
    assert.throws(() => assertRequestedBoardFocus({
      ...sheet, focused_document: { ...sheet.focused_document, ...change },
    }, board, projectId));
  }
  assert.throws(() => assertRequestedBoardFocus({ ...sheet, project_id: 'other' }, board, projectId), /parent/);
  assert.throws(() => assertBoardSignature({ ...components, total: 10 }, board), /Complete/);
  assert.throws(() => assertBoardSignature({
    ...components, components: components.components.map((c) => c.designator === 'K1' ? { ...c, designator: 'K2' } : c),
  }, board), /duplicated/);
  assert.throws(() => assertBoardSignature({
    ...components, components: components.components.map((c) => c.designator === 'U1' ? { ...c, deviceName: 'other' } : c),
  }, board), /marker/);
});

test('context rechecks accept unchanged evidence and reject project, focus and component drift', async () => {
  await ensureContext(mockClient(), baseline);
  await ensureContext(mockClient({ easyeda_project_list: listed }), { ...baseline, unlisted: false });
  for (const overrides of [
    { easyeda_project_list: { ...unlisted, activeProjectId: 'other' } },
    { easyeda_project_list: { ...unlisted, complete: false } },
    { easyeda_project_list: listed },
    { easyeda_schematic_sheet_info: { ...sheet, focused_document: { ...sheet.focused_document, uuid: 'pcb-2' } } },
    { easyeda_schematic_sheet_info: { ...sheet, focused_document: { ...sheet.focused_document, name: 'PCB_UI' } } },
    { easyeda_schematic_sheet_info: { ...sheet, focused_document: { ...sheet.focused_document, parentProjectUuid: 'other' } } },
    { easyeda_pcb_components: { ...components, components: components.components.map((c) => c.designator === 'K1' ? { ...c, deviceName: 'changed' } : c) } },
    { easyeda_pcb_components: { ...components, components: [] } },
  ]) {
    await assert.rejects(ensureContext(mockClient(overrides), baseline), ContextDriftError);
  }
  await assert.rejects(ensureContext(mockClient(), { ...baseline, unlisted: false }), ContextDriftError);
});

test('an actually used override never updates the shared revision manifest even for a complete bundle', async () => {
  const manifestPath = fileURLToPath(new URL('../smart_power_strip/configs/revision_manifest.json', import.meta.url));
  const before = await readFile(manifestPath);
  const result = await maybeUpdateRevisionManifest({
    projectId, baseManifestHash: 'irrelevant', hashedFiles: [], complete: true, unlistedOverrideUsed: true,
  });
  assert.equal(result.updated, false);
  assert.match(result.reason, /unlisted/);
  assert.deepEqual(await readFile(manifestPath), before);
});
