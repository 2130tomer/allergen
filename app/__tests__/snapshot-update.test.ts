const mockFiles = new Map<string, string>();
let mockDownload = 'valid';
let mockMoveFails = false;
const directory = 'file:///documents/SQLite/';
const active = `${directory}allergen-snapshot.sqlite`;
const backup = `${directory}snapshot-backup.sqlite`;

jest.mock('expo-asset', () => ({ Asset: { fromModule: jest.fn() } }));
jest.mock('expo-file-system', () => ({
  documentDirectory: 'file:///documents/',
  getInfoAsync: jest.fn(async (path: string) => ({ exists: mockFiles.has(path) })),
  makeDirectoryAsync: jest.fn(async () => undefined),
  deleteAsync: jest.fn(async (path: string) => { mockFiles.delete(path); }),
  copyAsync: jest.fn(async ({ from, to }: { from: string; to: string }) => {
    const data = mockFiles.get(from);
    if (data === undefined) throw new Error('missing source');
    mockFiles.set(to, data);
  }),
  moveAsync: jest.fn(async ({ from, to }: { from: string; to: string }) => {
    if (mockMoveFails) throw new Error('move failed');
    mockFiles.set(to, mockFiles.get(from) as string); mockFiles.delete(from);
  }),
  downloadAsync: jest.fn(async (_url: string, to: string) => {
    mockFiles.set(to, mockDownload); return { status: 200 };
  }),
}));
jest.mock('expo-sqlite', () => ({
  openDatabaseAsync: jest.fn(async (name: string) => ({
    execAsync: jest.fn(async () => undefined),
    closeAsync: jest.fn(async () => undefined),
    getFirstAsync: jest.fn(async (sql: string) => {
      const data = mockFiles.get(`file:///documents/SQLite/${name}`);
      if (sql === 'PRAGMA integrity_check') return { integrity_check: data === 'broken' ? 'failed' : 'ok' };
      if (sql === 'PRAGMA foreign_key_check') return null;
      if (sql.includes('COUNT(*)')) return { total: 1000, with_data: data === 'empty' ? 0 : data === 'drop' ? 100 : 400 };
      return null;
    }),
    getAllAsync: jest.fn(async () => {
      const data = mockFiles.get(`file:///documents/SQLite/${name}`);
      return Object.entries({ schema_version: data === 'legacy' ? '1' : '2', product_count: '1000',
        with_allergen_data: data === 'empty' ? '0' : data === 'drop' ? '100' : '400', built_at: '2026-09-05' })
        .map(([key, value]) => ({ key, value }));
    }),
  })),
}));

import { installBundledSnapshot, replaceSnapshotFrom } from '../src/db/bootstrap';

beforeEach(() => {
  mockFiles.clear(); mockFiles.set(active, 'original'); mockDownload = 'valid'; mockMoveFails = false;
});

test.each(['broken', 'legacy', 'empty', 'drop'])('rejects %s download without changing active catalog', async (candidate) => {
  mockDownload = candidate;
  expect((await replaceSnapshotFrom('https://example.org/snapshot')).kind).toBe('failed');
  expect(mockFiles.get(active)).toBe('original');
});
test('successful update preserves backup', async () => {
  expect((await replaceSnapshotFrom('https://example.org/snapshot')).kind).toBe('ready');
  expect(mockFiles.get(active)).toBe('valid');
  expect(mockFiles.get(backup)).toBe('original');
});
test('failed promotion restores active catalog', async () => {
  mockMoveFails = true;
  expect((await replaceSnapshotFrom('https://example.org/snapshot')).kind).toBe('failed');
  expect(mockFiles.get(active)).toBe('original');
});
test('startup recovers a backup after interrupted replacement', async () => {
  mockFiles.delete(active); mockFiles.set(backup, 'original');
  expect((await installBundledSnapshot()).kind).toBe('ready');
  expect(mockFiles.get(active)).toBe('original');
});
