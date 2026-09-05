import { fetchFromOpenFoodFacts, mapTags } from '../src/net/openFoodFacts';
const barcode = '7290000066318';
const originalFetch = globalThis.fetch;
afterEach(() => { globalThis.fetch = originalFetch; });
function response(body: unknown, status = 200): void {
  globalThis.fetch = jest.fn().mockResolvedValue({ ok: status === 200, status, json: async () => body });
}
test('confirmed missing is null', async () => {
  response({ status: 0 }, 404);
  await expect(fetchFromOpenFoodFacts(barcode)).resolves.toBeNull();
});
test('outage is not a missing product', async () => {
  response({}, 503);
  await expect(fetchFromOpenFoodFacts(barcode)).rejects.toMatchObject({ kind: 'service' });
});
test('network failure is not a missing product', async () => {
  globalThis.fetch = jest.fn().mockRejectedValue(new Error('offline'));
  await expect(fetchFromOpenFoodFacts(barcode)).rejects.toMatchObject({ kind: 'network' });
});
test('wrong barcode is rejected', async () => {
  response({ status: 1, product: { code: 'wrong' } });
  await expect(fetchFromOpenFoodFacts(barcode)).rejects.toMatchObject({ kind: 'invalid' });
});
test('malformed payload is rejected', async () => {
  response({ error: 'temporary error' });
  await expect(fetchFromOpenFoodFacts(barcode)).rejects.toMatchObject({ kind: 'invalid' });
});
test('multilingual tags use the pipeline dictionary', () => {
  expect(mapTags(['fr:lait', 'de:erdnuss'])).toEqual(['milk', 'peanuts']);
});
